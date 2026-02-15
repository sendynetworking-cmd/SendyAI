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

    // Helper to find "Get Started" or "Pro" style buttons
    const isPricingButton = (el) => {
        const text = el.textContent || '';
        const lowerText = text.toLowerCase();
        // Match common button variations in the Framer export
        const matchesText = lowerText.includes('get started') ||
            lowerText.includes('upgrade') ||
            lowerText.includes('sync pro status') ||
            lowerText.includes('current plan');

        // Ensure it's likely a button (has a link or a framer attribute)
        return matchesText && (el.tagName === 'A' || el.hasAttribute('data-framer-name'));
    };

    const isProButton = (el) => {
        let p = el;
        while (p && p !== document.body) {
            if (p.textContent.includes('Pro') && !p.textContent.includes('Free Plan')) return true;
            p = p.parentElement;
        }
        return false;
    };

    const updateBtnText = (btn, text) => {
        if (!btn) return;
        const p = btn.querySelector('p');
        if (p) p.textContent = text;
        else btn.textContent = text;
    };

    // 1. GLOBAL CLICK DELEGATION (Reliable even if DOM changes)
    document.addEventListener('click', (e) => {
        // Look for the starting element or its ancestors that look like our buttons
        let btn = e.target;
        while (btn && btn !== document.body && !isPricingButton(btn)) {
            btn = btn.parentElement;
        }

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

    // 2. STATUS & SYNC LOGIC
    if (extensionKey) {
        if (localKey && localKey !== extensionKey) {
            try {
                const localUser = await fetch(`https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`).then(r => r.json());
                if (localUser.paidAt) {
                    console.log('[Home] Sync required: Browser is Pro, Extension is not.');
                    // Find Pro buttons to update text
                    document.querySelectorAll('a, [data-framer-name]').forEach(el => {
                        if (isPricingButton(el) && isProButton(el)) {
                            updateBtnText(el, 'Sync Pro Status');
                            el.style.background = '#10b981';
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
    if (user.paid) {
        document.querySelectorAll('a, [data-framer-name]').forEach(el => {
            if (isPricingButton(el)) {
                const isPro = isProButton(el);
                updateBtnText(el, isPro ? 'Current Plan' : 'Free Tier');
                el.style.pointerEvents = 'none';
                el.style.opacity = '0.7';
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', init);
