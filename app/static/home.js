const extpay = ExtPay('sendyai');

async function init() {
    // Capture identity from extension if provided
    const urlParams = new URLSearchParams(window.location.search);
    const apiKey = urlParams.get('api_key');
    if (apiKey) {
        localStorage.setItem('extensionpay_api_key', JSON.stringify(apiKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const user = await extpay.getUser();
    const btnFree = document.getElementById('btn-free');
    const btnPro = document.getElementById('btn-pro');

    if (user.paid) {
        btnPro.textContent = 'Current Plan';
        btnPro.disabled = true;
        btnFree.textContent = 'Free Tier';
        btnFree.disabled = true;
    }

    btnPro.addEventListener('click', () => {
        extpay.openPaymentPage();
    });
}

document.addEventListener('DOMContentLoaded', init);
