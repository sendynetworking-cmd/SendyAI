/**
 * Sendy AI — Home Page Script
 * Handles payment integration via ExtensionPay.
 */

let extpay;
try {
    extpay = ExtPay('sendyai');
} catch (e) {
    console.log('[Home] ExtPay not available');
}

document.addEventListener('DOMContentLoaded', async () => {
    // All pricing buttons open the payment page
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pricing-btn');
        if (!btn) return;

        e.preventDefault();
        e.stopPropagation();

        if (extpay) {
            try {
                extpay.openPaymentPage();
            } catch (err) {
                console.error('[Home] Payment error:', err);
            }
        }
    }, { capture: true });

    // If user is already paid, update button states
    if (extpay) {
        try {
            const user = await extpay.getUser();
            if (user.paid) {
                document.querySelectorAll('.pricing-btn').forEach(btn => {
                    const isPro = btn.closest('.pricing-card.featured') !== null;
                    btn.textContent = isPro ? 'Current Plan' : 'Free Tier';
                    btn.style.pointerEvents = 'none';
                    btn.style.opacity = '0.7';
                });
            }
        } catch (e) {
            console.log('[Home] Could not check payment status');
        }
    }
});
