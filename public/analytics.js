// PostHog — loaded in <head> on every page, above styles.css.
// phc_* is a public client-side project key; it is meant to ship in the page.
// Loader copied verbatim from the project's own dashboard snippet — it stubs
// every method the current posthog-js exposes, so calls made before array.js
// finishes loading are queued instead of throwing.
!function(t,e){var o,n,p,r;e.__SV||(window.posthog && window.posthog.__loaded)||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}p||((p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",p.onerror=function(){p=null},(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r));var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="Sn Cn init Hn Un Gn Yi zn Kn qn capture Vn kn calculateEventProperties es register register_once register_for_session unregister unregister_for_session os Bn ss getFeatureFlag getFeatureFlagPayload getFeatureFlagResult getAllFeatureFlags isFeatureEnabled reloadFeatureFlags updateFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSurveysLoaded onSessionId getSurveys getActiveMatchingSurveys renderSurvey displaySurvey cancelPendingSurvey canRenderSurvey canRenderSurveyAsync ls identify setPersonProperties unsetPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset us shutdown setIdentity clearIdentity get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException addExceptionStep captureLog startExceptionAutocapture stopExceptionAutocapture loadToolbar get_property getSessionProperty rs Xn createPersonProfile setInternalOrTestUser ns $n vs opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing get_explicit_consent_status is_capturing clear_opt_in_out_capturing Jn debug tr At getPageViewId captureTraceFeedback captureTraceMetric Ln".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);

posthog.init('phc_zkok9vcaQPAeRLYb7kDJshkUJmNcvvphwCLSakFSDHTi', {
  api_host: 'https://us.i.posthog.com',
  defaults: '2026-05-30',
  person_profiles: 'identified_only',

  // Events from these hosts are still sent — so you can confirm tracking works
  // while developing — but arrive flagged as internal, and the project's
  // "Filter out internal and test users" setting hides them from insights.
  internal_or_test_user_hostname: ['localhost', '127.0.0.1'],
});

// One-time self-exclusion for the live site. Visit any page with ?ph=off to
// stop being tracked on this browser (persists in localStorage), ?ph=on to undo.
// PostHog cannot otherwise tell you apart from a real visitor — nothing here
// ever calls identify(), so you are anonymous in your own dashboard.
(function () {
  var flag = new URLSearchParams(window.location.search).get('ph');
  if (flag === 'off') posthog.opt_out_capturing();
  if (flag === 'on') posthog.opt_in_capturing();
})();

// Custom events. Autocapture already records raw clicks; these are the ones
// worth naming, so they can be used as goals without hunting through selectors.
document.addEventListener('DOMContentLoaded', function () {
  document.addEventListener('click', function (e) {
    var link = e.target.closest && e.target.closest('a[href]');
    if (!link) return;

    if (link.hasAttribute('download')) {
      posthog.capture('document downloaded', {
        file: link.getAttribute('href').split('/').pop(),
        location: window.location.pathname,
      });
      return;
    }

    var href = link.getAttribute('href') || '';
    if (href.indexOf('mailto:') === 0) {
      posthog.capture('email link clicked', { location: window.location.pathname });
      return;
    }

    if (link.hostname && link.hostname !== window.location.hostname) {
      posthog.capture('outbound link clicked', {
        url: link.href,
        domain: link.hostname,
        location: window.location.pathname,
      });
    }
  });
});
