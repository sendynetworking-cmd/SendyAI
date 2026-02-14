const extpay = ExtPay('sendyai');

async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const extensionKey = urlParams.get('api_key');
    let localKey = localStorage.getItem('extensionpay_api_key');
    if (localKey) {
        try { localKey = JSON.parse(localKey); } catch (e) { }
    }

    const pricingButtons = document.querySelectorAll('.pricing-button');
    const extensionId = 'cljgofleblhgmbhgloagholbpojhflja';
    const updateBtnText = (btn, text) => {
        if (!btn) return;
        const p = btn.querySelector('p');
        if (p) p.textContent = text;
        else btn.textContent = text;
    }

    // Scenario: User visited from extension with a key
    if (extensionKey) {
        if (localKey && localKey !== extensionKey) {
            try {
                const localUser = await fetch(`https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`).then(r => r.json());
                if (localUser.paidAt) {
                    console.log('[Home] Sync required: Browser is Pro, Extension is not.');
                    pricingButtons.forEach(btn => {
                        if (btn.classList.contains('btn-pro')) {
                            updateBtnText(btn, 'Sync Pro Status');
                            btn.style.background = '#10b981';
                            btn.addEventListener('click', (e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                chrome.runtime.sendMessage(extensionId, { action: 'syncPaidKey', apiKey: localKey }, (res) => {
                                    if (res?.success) alert('Pro Status Synced!');
                                });
                            });
                        }
                    });
                    return;
                }
            } catch (e) { }
        }
        localStorage.setItem('extensionpay_api_key', JSON.stringify(extensionKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const user = await extpay.getUser();
    pricingButtons.forEach(btn => {
        // 1. Text updates based on user status
        if (user.paid) {
            updateBtnText(btn, btn.classList.contains('btn-pro') ? 'Current Plan' : 'Free Tier');
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.7';
        }

        // 2. Default Click Handler for Payment
        btn.addEventListener('click', (e) => {
            console.log('[Home] Pricing click -> opening payment page');
            e.preventDefault();
            e.stopPropagation();
            try {
                extpay.openPaymentPage();
            } catch (err) {
                console.error('[Home] Payment error:', err);
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', init);
