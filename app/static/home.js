const extpay = ExtPay('sendyai');

async function init() {
    const pricingGrid = document.getElementById('pricing-grid');

    try {
        const [user, plans] = await Promise.all([
            extpay.getUser(),
            extpay.getPlans()
        ]);

        // Clear loading state
        pricingGrid.innerHTML = '';

        // 1. Render Free Plan (Always exists)
        renderPlanCard({
            name: 'Free Plan',
            price: 0,
            features: [
                '3 Unified Credits / week',
                'Email Lookups Included',
                'AI Outreach Generation'
            ],
            isCurrent: !user.paid,
            buttonText: !user.paid ? 'Current Plan' : 'Free Tier',
            buttonClass: 'btn-secondary',
            disabled: true
        });

        // 2. Render ExtensionPay Plans (Pro, etc.)
        plans.forEach(plan => {
            // Determine features based on plan name (could be more dynamic if description is used)
            const features = [
                '50 Unified Credits / week',
                'Email Lookups Included',
                'Latest AI Models',
                'AI Email Generation'
            ];

            const isCurrent = user.paid && user.plan && (user.plan.id === plan.id);

            renderPlanCard({
                name: plan.name,
                price: plan.price,
                features: features,
                isCurrent: isCurrent,
                buttonText: isCurrent ? 'Current Plan' : `Upgrade to ${plan.name}`,
                buttonClass: 'btn-primary',
                disabled: isCurrent,
                onClick: () => extpay.openPaymentPage()
            });
        });

    } catch (err) {
        console.error('Failed to load plans:', err);
        pricingGrid.innerHTML = `<p style="color: var(--text-red); text-align: center; grid-column: 1/-1;">Error loading plans. Please try refreshing.</p>`;
    }
}

function renderPlanCard(config) {
    const pricingGrid = document.getElementById('pricing-grid');
    const card = document.createElement('div');
    card.className = 'card pricing-card animate-in';
    if (config.buttonClass === 'btn-primary') {
        card.style.borderColor = 'var(--accent-violet)';
    }

    const featuresHtml = config.features.map(f => `
        <li>
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
            </svg>
            ${f}
        </li>
    `).join('');

    card.innerHTML = `
        <div class="card-body">
            <div class="tier-header">
                <div class="tier-name">${config.name}</div>
                <div class="tier-price">$${config.price}<span>/mo</span></div>
            </div>
            <ul class="features-list">
                ${featuresHtml}
            </ul>
            <button class="btn ${config.buttonClass} btn-block" 
                    ${config.disabled ? 'disabled' : ''} 
                    id="btn-${config.name.toLowerCase().replace(/\s+/g, '-')}">
                ${config.buttonText}
            </button>
        </div>
    `;

    if (config.onClick && !config.disabled) {
        card.querySelector('button').addEventListener('click', config.onClick);
    }

    pricingGrid.appendChild(card);
}

document.addEventListener('DOMContentLoaded', init);
