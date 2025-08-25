document.addEventListener('DOMContentLoaded', function () {
	function initializePasswordToggles() {
		const togglePasswordButtons = document.querySelectorAll('.toggle-password')
		togglePasswordButtons.forEach(button => {
			button.addEventListener('click', function () {
				const parent =
					this.closest('.form-group') || this.closest('.password-wrapper')
				if (!parent) return

				const passwordInput = parent.querySelector('input')
				if (!passwordInput) return

				if (passwordInput.type === 'password') {
					passwordInput.type = 'text'
					this.textContent = '🙈'
				} else {
					passwordInput.type = 'password'
					this.textContent = '👁️'
				}
			})
		})
	}
	function setupBotControlForms() {
		const startForm = document.querySelector('form[action*="start-bot"]')
		const stopForm = document.querySelector('form[action*="stop-bot"]')

		if (startForm) {
			startForm.addEventListener('submit', function () {
				const button = startForm.querySelector('button[type="submit"]')
				if (button) {
					button.disabled = true
					button.textContent = 'Запускаем...'
				}
			})
		}

		if (stopForm) {
			stopForm.addEventListener('submit', function () {
				const button = stopForm.querySelector('button[type="submit"]')
				if (button) {
					button.disabled = true
					button.textContent = 'Останавливаем...'
				}
			})
		}
	}
	function setupConfirmationForms() {
		const confirmationForms = document.querySelectorAll('form[data-confirm]')
		confirmationForms.forEach(form => {
			form.addEventListener('submit', function (event) {
				const message = form.getAttribute('data-confirm')
				if (!confirm(message)) {
					event.preventDefault()
				}
			})
		})
	}
	function initializeDashboardCharts() {
		const usersChartCanvas = document.getElementById('newUsersChart')
		if (!usersChartCanvas || typeof CHART_DATA === 'undefined') {
			return
		}
		function prepareChartData(data, label, color) {
			const labels = []
			const values = []
			const today = new Date()

			for (let i = 29; i >= 0; i--) {
				const date = new Date(today)
				date.setDate(today.getDate() - i)
				const dateString = date.toISOString().split('T')[0]
				labels.push(dateString)
				values.push(data[dateString] || 0)
			}

			return {
				labels: labels,
				datasets: [
					{
						label: label,
						data: values,
						borderColor: color,
						backgroundColor: color + '33',
						borderWidth: 2,
						fill: true,
						tension: 0.3,
					},
				],
			}
		}
		const usersCtx = usersChartCanvas.getContext('2d')
		const usersChartData = prepareChartData(
			CHART_DATA.users,
			'Новых пользователей в день',
			'#007bff'
		)
		new Chart(usersCtx, {
			type: 'line',
			data: usersChartData,
			options: {
				scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
				responsive: true,
			},
		})
		const keysChartCanvas = document.getElementById('newKeysChart')
		if (!keysChartCanvas) return

		const keysCtx = keysChartCanvas.getContext('2d')
		const keysChartData = prepareChartData(
			CHART_DATA.keys,
			'Новых ключей в день',
			'#28a745'
		)
		new Chart(keysCtx, {
			type: 'line',
			data: keysChartData,
			options: {
				scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
				responsive: true,
			},
		})
	}
	initializePasswordToggles()
	setupBotControlForms()
	setupConfirmationForms()
	initializeDashboardCharts()
})
