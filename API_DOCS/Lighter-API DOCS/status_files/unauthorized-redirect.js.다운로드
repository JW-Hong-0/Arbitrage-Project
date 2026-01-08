/**
 * Centralized handler for unauthorized (401) responses.
 * Intercepts fetch and XMLHttpRequest to redirect to login page when session expires.
 * My attempt to bring something like useUnauthorizedRedirect hook in React, to our
 * legacy angular code.
 *
 * This file is used to redirect the user to the login page when their session expires
 * for the inactive session timeout feature: https://github.com/readmeio/readme/pull/16532
 */

(function () {
  'use strict';

  // Track if we're already redirecting to prevent multiple redirects
  let isRedirecting = false;

  /**
   * Check if a URL is an API endpoint
   * @param {string} url - URL to check
   * @returns {boolean} true if the URL is an API endpoint
   */
  function isApiUrl(url) {
    if (!url) return false;
    // Check for common API path patterns
    return (
      url.startsWith('/api') ||
      url.startsWith('/v1/') ||
      url.startsWith('/v2/') ||
      url.startsWith('/api-next/') ||
      url.includes('/api/')
    );
  }

  /**
   * Handle 401 response by redirecting to login URL
   * @param {string} loginUrl - URL to redirect to
   * @param {string} expiryReason - Reason for expiry (e.g., 'inactive')
   */
  function handleUnauthorized(loginUrl, expiryReason) {
    if (isRedirecting || !loginUrl || !expiryReason) {
      return;
    }

    isRedirecting = true;

    // Temporarily override beforeunload to prevent confirmation dialogs
    // Store the original handler if it exists
    window.onbeforeunload = null;

    // Defer the redirect with a small timeout to allow components to clean up
    // and to avoid race conditions with beforeunload listeners
    setTimeout(function () {
      try {
        // Handle both absolute and relative URLs
        let url;
        if (loginUrl.startsWith('http://') || loginUrl.startsWith('https://')) {
          url = new URL(loginUrl);
        } else {
          url = new URL(loginUrl, window.location.origin);
        }

        // If the redirect parameter is an API endpoint, replace it with the current page
        const redirectParam = url.searchParams.get('redirect');
        if (redirectParam && isApiUrl(redirectParam)) {
          const currentPage = window.location.pathname + window.location.search;
          url.searchParams.set('redirect', currentPage);
        }

        // Add timeoutReason if not already present
        if (!url.searchParams.has('timeoutReason')) {
          url.searchParams.set('timeoutReason', expiryReason);
        }

        // Use window.location.replace() instead of assign() to avoid triggering beforeunload
        // replace() doesn't add to history and may not trigger beforeunload in some browsers
        window.location.replace(url.toString());
      } catch (e) {
        // Fallback to direct replacement if URL parsing fails
        console.error('Error parsing login URL:', e);
        window.location.replace(loginUrl);
      }
    }, 100);
  }

  /**
   * Intercept fetch API calls
   */
  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    return originalFetch.apply(this, args).then(
      response => {
        // Check for 401 status
        if (response.status === 401) {
          const loginUrl = response.headers.get('X-Login-Url');
          const expiryReason = response.headers.get('X-Expiry-Reason');

          // only redirect if we have a login URL and expiry reason
          if (loginUrl && expiryReason) {
            handleUnauthorized(loginUrl, expiryReason);
            return Promise.reject(new Error('Session expired'));
          }
        }
        return response;
      },
      error => {
        // Re-throw fetch errors
        throw error;
      },
    );
  };

  /**
   * Intercept XMLHttpRequest for Angular $http and other XHR-based requests
   */
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this._url = url;
    return originalOpen.apply(this, [method, url, ...rest]);
  };

  XMLHttpRequest.prototype.send = function (...args) {
    const xhr = this;

    // Check for 401 responses after the request completes
    const checkUnauthorized = function () {
      if (xhr.readyState === 4 && xhr.status === 401) {
        const loginUrl = xhr.getResponseHeader('X-Login-Url');
        const expiryReason = xhr.getResponseHeader('X-Expiry-Reason');

        if (loginUrl) {
          handleUnauthorized(loginUrl, expiryReason);
        }
      }
    };

    // Override onreadystatechange if it exists
    const originalOnReadyStateChange = xhr.onreadystatechange;
    xhr.onreadystatechange = function () {
      checkUnauthorized();

      // Call original handler if it exists
      if (originalOnReadyStateChange) {
        originalOnReadyStateChange.apply(this, arguments);
      }
    };

    // Also intercept addEventListener for load/loadend events
    const originalAddEventListener = xhr.addEventListener;
    xhr.addEventListener = function (type, listener, options) {
      if (type === 'load' || type === 'loadend') {
        const wrappedListener = function (event) {
          checkUnauthorized();
          if (listener) {
            listener.call(this, event);
          }
        };
        return originalAddEventListener.call(this, type, wrappedListener, options);
      }
      return originalAddEventListener.call(this, type, listener, options);
    };

    return originalSend.apply(this, args);
  };
})();
