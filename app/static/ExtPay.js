var ExtPay = (function () {
    'use strict';

    var commonjsGlobal = typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : {};

    function createCommonjsModule(fn) {
        var module = { exports: {} };
        return fn(module, module.exports), module.exports;
    }

    var browserPolyfill = createCommonjsModule(function (module, exports) {
        (function (global, factory) {
            factory(module);
        })(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : commonjsGlobal, function (module) {
            if (typeof browser === "undefined" || Object.getPrototypeOf(browser) !== Object.prototype) {
                const CHROME_SEND_MESSAGE_CALLBACK_NO_RESPONSE_MESSAGE = "The message port closed before a response was received.";
                const wrapAPIs = extensionAPIs => {
                    const apiMetadata = {
                        "runtime": {
                            "sendMessage": { "minArgs": 1, "maxArgs": 3 },
                            "onMessage": { "minArgs": 1, "maxArgs": 1 }
                        },
                        "storage": {
                            "local": { "get": { "minArgs": 0, "maxArgs": 1 }, "set": { "minArgs": 1, "maxArgs": 1 } },
                            "sync": { "get": { "minArgs": 0, "maxArgs": 1 }, "set": { "minArgs": 1, "maxArgs": 1 } }
                        },
                        "tabs": { "create": { "minArgs": 1, "maxArgs": 1 } },
                        "windows": { "getCurrent": { "minArgs": 0, "maxArgs": 1 } }
                    };

                    const wrapAsyncFunction = (name, metadata) => {
                        return function asyncFunctionWrapper(target, ...args) {
                            return new Promise((resolve, reject) => {
                                const callback = (...callbackArgs) => {
                                    if (extensionAPIs.runtime.lastError) {
                                        reject(extensionAPIs.runtime.lastError);
                                    } else {
                                        resolve(callbackArgs[0]);
                                    }
                                };
                                target[name](...args, callback);
                            });
                        };
                    };

                    const wrapObject = (target, wrappers = {}, metadata = {}) => {
                        let cache = Object.create(null);
                        let handlers = {
                            get(proxyTarget, prop) {
                                if (prop in cache) return cache[prop];
                                if (!(prop in target)) return undefined;
                                let value = target[prop];
                                if (typeof value === "function") {
                                    if (metadata[prop]) {
                                        const wrapper = wrapAsyncFunction(prop, metadata[prop]);
                                        value = (...args) => wrapper(target, ...args);
                                    } else {
                                        value = value.bind(target);
                                    }
                                } else if (typeof value === "object" && value !== null && metadata[prop]) {
                                    value = wrapObject(value, wrappers[prop], metadata[prop]);
                                }
                                cache[prop] = value;
                                return value;
                            }
                        };
                        return new Proxy(Object.create(target), handlers);
                    };

                    return wrapObject(extensionAPIs, {}, apiMetadata);
                };
                module.exports = wrapAPIs(chrome);
            } else {
                module.exports = browser;
            }
        });
    });

    // For running as a content script on extensionpay.com
    if (typeof window !== 'undefined') {
        window.addEventListener('message', (event) => {
            if (event.origin !== 'https://extensionpay.com') return;
            if (event.data === 'extpay-fetch-user' || event.data === 'extpay-trial-start') {
                chrome.runtime.sendMessage(event.data);
            }
        }, false);
    }

    function ExtPay(extension_id) {
        const HOST = 'https://extensionpay.com';
        const EXTENSION_URL = `${HOST}/extension/${extension_id}`;
        const paid_callbacks = [];

        async function get(key) {
            const keys = Array.isArray(key) ? key : [key];
            const res = {};

            // 1. Try Native Chrome Storage (Resilient check)
            try {
                if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                    return new Promise(resolve => {
                        chrome.storage.local.get(key, (items) => {
                            if (chrome.runtime.lastError) resolve({});
                            else resolve(items || {});
                        });
                    });
                }
            } catch (e) {
                // Extension storage not available
            }

            // 2. Fallback to localStorage
            if (typeof localStorage !== 'undefined') {
                keys.forEach(k => {
                    const val = localStorage.getItem(k);
                    if (val) {
                        try { res[k] = JSON.parse(val); } catch (e) { res[k] = val; }
                    }
                });
            }
            return res;
        }

        async function set(dict) {
            // 1. Try Native Chrome Storage
            try {
                if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
                    return new Promise(resolve => {
                        chrome.storage.local.set(dict, resolve);
                    });
                }
            } catch (e) {
                // Extension storage not available
            }

            // 2. Fallback to localStorage
            if (typeof localStorage !== 'undefined') {
                for (const key in dict) {
                    localStorage.setItem(key, JSON.stringify(dict[key]));
                }
            }
        }

        async function fetch_user() {
            try {
                const storage = await get(['extensionpay_api_key']);
                const api_key = storage.extensionpay_api_key;
                if (!api_key) return { paid: false };

                const resp = await fetch(`${EXTENSION_URL}/api/v2/user?api_key=${api_key}`);
                if (!resp.ok) return { paid: false };
                const user_data = await resp.json();
                await set({ extensionpay_user: user_data });

                if (user_data.paidAt) {
                    paid_callbacks.forEach(cb => cb(user_data));
                }

                return user_data;
            } catch (e) {
                return { paid: false };
            }
        }

        async function get_plans() {
            try {
                const resp = await fetch(`${EXTENSION_URL}/api/v2/plans`);
                if (!resp.ok) return [];
                return await resp.json();
            } catch (e) {
                return [];
            }
        }

        return {
            getUser: fetch_user,
            getPlans: get_plans,
            onPaid: {
                addListener: (cb) => paid_callbacks.push(cb)
            },
            openPaymentPage: async () => {
                let api_key = null;
                try {
                    const storage = await get(['extensionpay_api_key']);
                    api_key = storage.extensionpay_api_key;

                    if (!api_key) {
                        const resp = await fetch(`${EXTENSION_URL}/api/new-key`, { method: 'POST' });
                        if (resp.ok) {
                            api_key = await resp.json();
                            await set({ extensionpay_api_key: api_key });
                        }
                    }
                } catch (e) {
                    console.warn('ExtensionPay: Could not fetch API key (likely CORS or web context), opening payment page without key.');
                }

                const url = api_key
                    ? `${EXTENSION_URL}/choose-plan?api_key=${api_key}`
                    : `${EXTENSION_URL}/choose-plan`;

                if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
                    chrome.tabs.create({ url });
                } else {
                    window.open(url, '_blank');
                }
            },
            startBackground: () => {
                chrome.runtime.onMessage.addListener((message) => {
                    if (message === 'extpay-fetch-user') fetch_user();
                });
            }
        };
    }

    return ExtPay;
})();

if (typeof globalThis !== 'undefined') { globalThis.ExtPay = ExtPay; }
if (typeof self !== 'undefined') { self.ExtPay = ExtPay; }
