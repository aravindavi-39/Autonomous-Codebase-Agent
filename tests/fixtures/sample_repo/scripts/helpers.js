/**
 * Helper utilities for the frontend.
 */

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US');
}

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

module.exports = { formatDate, debounce };
