const extpay = ExtPay('sendyai');

function updateBtnText(btn, text) {
    if (!btn) return;
    const p = btn.querySelector('p');
    if (p) p.textContent = text;
    else btn.textContent = text;
}

async function init() {
    console.log('[Home] ExtensionPay Integration Initializing...');
    const urlParams = new URLSearchParams(window.location.search);
    const extensionKey = urlParams.get('api_key');
    let localKey = localStorage.getItem('extensionpay_api_key');
    if (localKey) {
        try { localKey = JSON.parse(localKey); } catch (e) { }
    }

    const btnPros = document.querySelectorAll('.btn-pro');
    const btnFrees = document.querySelectorAll('.btn-free');

    // SCENARIO 1: Immediate Listener for Pro Buttons
    const handleProClick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log('[Home] Pro button clicked - Opening Payment Page');
        extpay.openPaymentPage();
    };

    btnPros.forEach(btn => {
        btn.style.cursor = 'pointer';
        // Remove any old listeners if this is called multiple times
        btn.removeEventListener('click', handleProClick);
        btn.addEventListener('click', handleProClick, true); // Use capture phase to beat Framer
    });

    // SCENARIO 2: Extension Sync Logic (if key present in URL)
    if (extensionKey) {
        console.log('[Home] Found api_key in URL, checking for sync conflicts...');
        if (localKey && localKey !== extensionKey) {
            try {
                const localUser = await fetch(`https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`).then(r => r.json());
                if (localUser.paidAt) {
                    console.log('[Home] Conflict: Browser has paid key, Extension does not. Offering sync.');
                    btnPros.forEach(btn => {
                        updateBtnText(btn, 'Sync Pro to Extension');
                        btn.style.background = '#10b981'; // Green
                        btn.style.pointerEvents = 'auto';
                        btn.removeEventListener('click', handleProClick, true);
                        btn.addEventListener('click', (e) => {
                            e.preventDefault();
                            chrome.runtime.sendMessage('cljgofleblhgmbhgloagholbpojhflja', {
                                action: 'syncPaidKey',
                                apiKey: localKey
                            }, (response) => {
                                if (response?.success) {
                                    alert('Pro Status Synced! You can now close this tab.');
                                    updateBtnText(btn, 'Synced & Ready');
                                    btn.style.pointerEvents = 'none';
                                } else {
                                    alert('Sync failed - ensure the extension is open.');
                                }
                            });
                        }, true);
                    });
                    return;
                }
            } catch (e) {
                console.warn('[Home] Conflict check failed:', e);
            }
        }
        localStorage.setItem('extensionpay_api_key', JSON.stringify(extensionKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // SCENARIO 3: Fetch status and update UI
    try {
        const user = await extpay.getUser();
        console.log('[Home] Current user status:', user);
        if (user.paid) {
            btnPros.forEach(btn => {
                updateBtnText(btn, 'Current Plan');
                btn.style.pointerEvents = 'none';
                btn.removeEventListener('click', handleProClick, true);
            });
            btnFrees.forEach(btn => {
                updateBtnText(btn, 'Free Tier');
                btn.style.pointerEvents = 'none';
            });
        }
    } catch (e) {
        console.error('[Home] Error fetching user status:', e);
    }
}

// Ensure init is called as soon as possible
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// GLOBAL FALLBACK HANDLER
window.addEventListener('click', (e) => {
    const proBtn = e.target.closest('.btn-pro');
    if (proBtn) {
        console.log('[Home] Global fallback intercepted Pro button click.');
        // If the button has pointer-events: none, this won't fire anyway.
        // If it's active, we want to make sure the payment page opens.
        // We only trigger if the button isn't already handled or if we suspect failure.
    }
}, true);
