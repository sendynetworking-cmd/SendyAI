/**
 * Sendy AI — Home Page Script
 * Handles payment integration and button state management.
 */

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

    // All pricing buttons have the class "pricing-btn"
    const pricingButtons = () => document.querySelectorAll('.pricing-btn');

    /**
     * Checks if a button is inside the Pro pricing card.
     */
    const isProButton = (el) => {
        return el.closest('.pricing-card.featured') !== null;
    };

    /**
     * Updates a button's text content.
     */
    const updateBtnText = (btn, text) => {
        btn.textContent = text;
    };

    // ── Global Click Delegation ──
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pricing-btn');
        if (!btn) return;

        const text = btn.textContent.toLowerCase();

        // Handle Sync Logic
        if (text.includes('sync pro status')) {
            console.log('[Home] Sync click detected');
            e.preventDefault();
            e.stopPropagation();
            chrome.runtime.sendMessage(extensionId, { action: 'syncPaidKey', apiKey: localKey }, (res) => {
                if (res?.success) alert('Pro Status Synced!');
            });
            return;
        }

        // Default Payment Logic
        if (text.includes('get started') || text.includes('upgrade')) {
            console.log('[Home] Pricing click -> opening payment page');
            e.preventDefault();
            e.stopPropagation();
            try {
                extpay.openPaymentPage();
            } catch (err) {
                console.error('[Home] Payment error:', err);
            }
        }
    }, { capture: true });

    // ── Status & Sync Logic ──
    if (extensionKey) {
        if (localKey && localKey !== extensionKey) {
            try {
                const localUser = await fetch(
                    `https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`
                ).then(r => r.json());

                if (localUser.paidAt) {
                    console.log('[Home] Sync required: Browser is Pro, Extension is not.');
                    pricingButtons().forEach(btn => {
                        if (isProButton(btn)) {
                            updateBtnText(btn, 'Sync Pro Status');
                            btn.style.background = '#10b981';
                        }
                    });
                    return;
                }
            } catch (e) { }
        }
        localStorage.setItem('extensionpay_api_key', JSON.stringify(extensionKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // ── Update Button States for Paid Users ──
    const user = await extpay.getUser();
    if (user.paid) {
        pricingButtons().forEach(btn => {
            const isPro = isProButton(btn);
            updateBtnText(btn, isPro ? 'Current Plan' : 'Free Tier');
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.7';
        });
    }
}

document.addEventListener('DOMContentLoaded', init);
