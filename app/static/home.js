const extpay = ExtPay('sendyai');

async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const extensionKey = urlParams.get('api_key');
    let localKey = localStorage.getItem('extensionpay_api_key');
    if (localKey) {
        try { localKey = JSON.parse(localKey); } catch (e) { }
    }

    const btnFrees = document.querySelectorAll('.btn-free');
    const btnPros = document.querySelectorAll('.btn-pro');

    const updateBtnText = (btn, text) => {
        if (!btn) return;
        const p = btn.querySelector('p');
        if (p) p.textContent = text;
        else btn.textContent = text;
    }

    const setBtnState = (btn, text, disabled = false, isConflict = false) => {
        if (!btn) return;
        updateBtnText(btn, text);
        if (disabled) btn.style.pointerEvents = 'none';

        if (isConflict) {
            btn.style.background = '#10b981'; // Green
            btn.style.borderColor = '#10b981';
            btn.onclick = (e) => {
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
            };
        } else {
            btn.onclick = (e) => {
                e.preventDefault();
                extpay.openPaymentPage();
            };
        }
    };

    // Scenario: User visited from extension with a key
    if (extensionKey) {
        // Check if the current browser already has a PAID identity
        if (localKey && localKey !== extensionKey) {
            const localUser = await fetch(`https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`).then(r => r.json());

            if (localUser.paidAt) {
                console.log('[Home] Conflict: Browser is Pro, but Extension is not. Showing Recovery.');
                btnPros.forEach(btn => setBtnState(btn, 'Sync Pro to Extension', false, true));
                return;
            }
        }

        // No conflict or local not paid, safe to use extension's key
        localStorage.setItem('extensionpay_api_key', JSON.stringify(extensionKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const user = await extpay.getUser();
    if (user.paid) {
        btnPros.forEach(btn => {
            updateBtnText(btn, 'Current Plan');
            btn.style.pointerEvents = 'none';
        });
        btnFrees.forEach(btn => {
            updateBtnText(btn, 'Free Tier');
            btn.style.pointerEvents = 'none';
        });
    } else {
        btnPros.forEach(btn => setBtnState(btn, 'Get Started'));
    }
}

document.addEventListener('DOMContentLoaded', init);
