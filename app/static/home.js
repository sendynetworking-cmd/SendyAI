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

document.addEventListener('DOMContentLoaded', () => {
    // All pricing + manage subscription buttons open ExtensionPay
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pricing-btn, .manage-sub-btn');
        if (!btn || !extpay) return;

        e.preventDefault();
        e.stopPropagation();

        try {
            extpay.openPaymentPage();
        } catch (err) {
            console.error('[Home] Payment error:', err);
        }
    }, { capture: true });
});
