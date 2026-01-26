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
        // Determine tier (Pro vs Elite)
        const tier = (user.plan && JSON.stringify(user.plan).toLowerCase().includes('elite')) ? 'elite' : 'pro';

        if (tier === 'pro') {
            btnPro.textContent = 'Current Plan';
            btnPro.disabled = true;
            btnFree.textContent = 'Free Tier';
            btnFree.disabled = true;
        } else if (tier === 'elite') {
            btnPro.textContent = 'Downgrade to Pro';
            // Elite logic would go here if we had an elite button
        }
    }

    btnPro.addEventListener('click', () => {
        extpay.openPaymentPage();
    });
}

document.addEventListener('DOMContentLoaded', init);
