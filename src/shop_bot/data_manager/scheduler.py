import asyncio
import logging

from datetime import datetime, timedelta

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot

from shop_bot.bot_controller import BotController
from shop_bot.data_manager import database
from shop_bot.modules import xui_api
from shop_bot.bot import keyboards

CHECK_INTERVAL_SECONDS = 300
NOTIFY_BEFORE_HOURS = {72, 48, 24, 1}
notified_users = {}

logger = logging.getLogger(__name__)

def format_time_left(hours: int) -> str:
    """Correctly formats the time left for the notification message."""
    if hours >= 24:
        days = hours // 24
        if days % 10 == 1 and days % 100 != 11:
            return f"{days} день"
        elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
            return f"{days} дня"
        else:
            return f"{days} дней"
    else:
        if hours % 10 == 1 and hours % 100 != 11:
            return f"{hours} час"
        elif 2 <= hours % 10 <= 4 and (hours % 100 < 10 or hours % 100 >= 20):
            return f"{hours} часа"
        else:
            return f"{hours} часов"

async def send_subscription_notification(bot: Bot, user_id: int, key_id: int, time_left_hours: int, expiry_date: datetime):
    try:
        time_text = format_time_left(time_left_hours)
        expiry_str = expiry_date.strftime('%d.%m.%Y в %H:%M')
        
        message = (
            f"⚠️ **Внимание!** ⚠️\n\n"
            f"Срок действия вашей подписки истекает через **{time_text}**.\n"
            f"Дата окончания: **{expiry_str}**\n\n"
            f"Продлите подписку, чтобы не остаться без доступа к VPN!"
        )
        
        builder = InlineKeyboardBuilder()
        builder.button(text="🔑 Мои ключи", callback_data="manage_keys")
        builder.button(text="➕ Продлить ключ", callback_data=f"extend_key_{key_id}")
        builder.adjust(2)
        
        await bot.send_message(chat_id=user_id, text=message, reply_markup=builder.as_markup(), parse_mode='Markdown')
        logger.info(f"Sent subscription notification to user {user_id} for key {key_id} ({time_left_hours} hours left).")
        
    except Exception as e:
        logger.error(f"Error sending subscription notification to user {user_id}: {e}")

async def check_expiring_subscriptions(bot: Bot):
    logger.info("Scheduler: Checking for expiring subscriptions...")
    current_time = datetime.now()
    all_keys = database.get_all_keys()
    
    for key in all_keys:
        try:
            expiry_date = datetime.fromisoformat(key['expiry_date'])
            time_left = expiry_date - current_time

            if time_left.total_seconds() < 0:
                continue

            total_hours_left = int(time_left.total_seconds() / 3600)
            user_id = key['user_id']
            key_id = key['key_id']

            for hours_mark in NOTIFY_BEFORE_HOURS:
                if hours_mark - 1 < total_hours_left <= hours_mark:
                    notified_users.setdefault(user_id, {}).setdefault(key_id, set())
                    
                    if hours_mark not in notified_users[user_id][key_id]:
                        await send_subscription_notification(bot, user_id, key_id, hours_mark, expiry_date)
                        notified_users[user_id][key_id].add(hours_mark)
                    break
                    
        except Exception as e:
            logger.error(f"Error processing expiry for key {key.get('key_id')}: {e}")

async def sync_keys_with_panels():
    logger.info("Scheduler: Starting sync with XUI panels...")
    total_affected_records = 0
    
    all_hosts = database.get_all_hosts()
    if not all_hosts:
        logger.info("Scheduler: No hosts configured in the database. Sync skipped.")
        return

    for host in all_hosts:
        host_name = host['host_name']
        logger.info(f"Scheduler: Processing host: '{host_name}'")
        
        try:
            api, inbound = xui_api.login_to_host(
                host_url=host['host_url'],
                username=host['host_username'],
                password=host['host_pass'],
                inbound_id=host['host_inbound_id']
            )

            if not api or not inbound:
                logger.error(f"Scheduler: Could not log in to host '{host_name}'. Skipping this host.")
                continue
            
            full_inbound_details = api.inbound.get_by_id(inbound.id)
            clients_on_server = {client.email: client for client in (full_inbound_details.settings.clients or [])}
            logger.info(f"Scheduler: Found {len(clients_on_server)} clients on the '{host_name}' panel.")

            keys_in_db = database.get_keys_for_host(host_name)
            
            for db_key in keys_in_db:
                key_email = db_key['key_email']
                
                server_client = clients_on_server.pop(key_email, None)

                if server_client:
                    server_expiry_ms = server_client.expiry_time
                    local_expiry_dt = datetime.fromisoformat(db_key['expiry_date'])
                    local_expiry_ms = int(local_expiry_dt.timestamp() * 1000)

                    if abs(server_expiry_ms - local_expiry_ms) > 1000:
                        database.update_key_status_from_server(key_email, server_client)
                        total_affected_records += 1
                        logger.info(f"Scheduler: Synced (updated) key '{key_email}' for host '{host_name}'.")
                else:
                    logger.warning(f"Scheduler: Key '{key_email}' for host '{host_name}' not found on server. Deleting from local DB.")
                    database.update_key_status_from_server(key_email, None)
                    total_affected_records += 1

            if clients_on_server:
                for orphan_email in clients_on_server.keys():
                    logger.warning(f"Scheduler: Found orphan client '{orphan_email}' on host '{host_name}' that is not tracked by the bot.")

        except Exception as e:
            logger.error(f"Scheduler: An unexpected error occurred while processing host '{host_name}': {e}", exc_info=True)
            
    logger.info(f"Scheduler: Sync with XUI panels finished. Total records affected: {total_affected_records}.")

async def periodic_subscription_check(bot_controller: BotController):
    logger.info("Scheduler has been started.")
    await asyncio.sleep(10)

    while True:
        try:
            await sync_keys_with_panels()

            if bot_controller.get_status().get("is_running"):
                bot = bot_controller.get_bot_instance()
                if bot:
                    await check_expiring_subscriptions(bot)
                else:
                    logger.warning("Scheduler: Bot is marked as running, but instance is not available.")
            else:
                logger.info("Scheduler: Bot is stopped, skipping user notifications.")

        except Exception as e:
            logger.error(f"Scheduler: An unhandled error occurred in the main loop: {e}", exc_info=True)
            
        logger.info(f"Scheduler: Cycle finished. Next check in {CHECK_INTERVAL_SECONDS} seconds.")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)