const extpay = ExtPay('sendyai');

async function init() {
    console.log('[Home] Script initialized');
    const urlParams = new URLSearchParams(window.location.search);
    const extensionKey = urlParams.get('api_key');
    let localKey = localStorage.getItem('extensionpay_api_key');
    if (localKey) {
        try { localKey = JSON.parse(localKey); } catch (e) { }
    }

    const extensionId = 'cljgofleblhgmbhgloagholbpojhflja';
    const updateBtnText = (btn, text) => {
        if (!btn) return;
        const p = btn.querySelector('p');
        if (p) p.textContent = text;
        else btn.textContent = text;
    }

    // 1. GLOBAL CLICK DELEGATION (Reliable even if DOM changes)
    // Use capture: true to catch events before Framer/React can stop them
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pricing-button');
        if (!btn) return;

        console.log('[Home] Pricing click -> opening payment page');
        e.preventDefault();
        e.stopPropagation();

        try {
            extpay.openPaymentPage();
        } catch (err) {
            console.error('[Home] Payment error:', err);
        }
    }, { capture: true });

    // 2. STATUS & SYNC LOGIC
    // Scenario: User visited from extension with a key
    if (extensionKey) {
        if (localKey && localKey !== extensionKey) {
            try {
                const localUser = await fetch(`https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`).then(r => r.json());
                if (localUser.paidAt) {
                    console.log('[Home] Sync required: Browser is Pro, Extension is not.');
                    // Note: This specific button logic will need to be re-applied if DOM changes
                    // but the global listener above handles the default payment flow.
                    const proBtns = document.querySelectorAll('.pricing-button.btn-pro');
                    proBtns.forEach(btn => {
                        updateBtnText(btn, 'Sync Pro Status');
                        btn.style.background = '#10b981';
                        // Add sync-specific click listener
                        btn.addEventListener('click', (ev) => {
                            ev.stopImmediatePropagation(); // Prevent standard payment flow
                            chrome.runtime.sendMessage(extensionId, { action: 'syncPaidKey', apiKey: localKey }, (res) => {
                                if (res?.success) alert('Pro Status Synced!');
                            });
                        }, { capture: true });
                    });
                    return;
                }
            } catch (e) { }
        }
        localStorage.setItem('extensionpay_api_key', JSON.stringify(extensionKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const user = await extpay.getUser();
    if (user.paid) {
        const pricingButtons = document.querySelectorAll('.pricing-button');
        pricingButtons.forEach(btn => {
            updateBtnText(btn, btn.classList.contains('btn-pro') ? 'Current Plan' : 'Free Tier');
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.7';
        });
    }
}

document.addEventListener('DOMContentLoaded', init);
