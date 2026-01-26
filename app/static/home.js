const extpay = ExtPay('sendyai');

async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const extensionKey = urlParams.get('api_key');
    let localKey = localStorage.getItem('extensionpay_api_key');
    if (localKey) {
        try { localKey = JSON.parse(localKey); } catch (e) { }
    }

    const btnFree = document.getElementById('btn-free');
    const btnPro = document.getElementById('btn-pro');

    // Scenario: User visited from extension with a key
    if (extensionKey) {
        // Check if the current browser already has a PAID identity
        if (localKey && localKey !== extensionKey) {
            const localUser = await fetch(`https://extensionpay.com/extension/sendyai/api/v2/user?api_key=${localKey}`).then(r => r.json());

            if (localUser.paidAt) {
                console.log('[Home] Conflict: Browser is Pro, but Extension is not. Showing Recovery.');
                btnPro.textContent = 'Sync Pro to Extension';
                btnPro.style.background = '#10b981'; // Green
                btnPro.style.borderColor = '#10b981';

                btnPro.onclick = () => {
                    chrome.runtime.sendMessage('cljgofleblhgmbhgloagholbpojhflja', {
                        action: 'syncPaidKey',
                        apiKey: localKey
                    }, (response) => {
                        if (response?.success) {
                            alert('Pro Status Synced! You can now close this tab.');
                            btnPro.textContent = 'Synced & Ready';
                            btnPro.disabled = true;
                        } else {
                            alert('Sync failed - ensure the extension is open.');
                        }
                    });
                };
                return;
            }
        }

        // No conflict or local not paid, safe to use extension's key
        localStorage.setItem('extensionpay_api_key', JSON.stringify(extensionKey));
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const user = await extpay.getUser();
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
