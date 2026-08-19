import * as Sentry from '@sentry/react-native';

// Inert until EXPO_PUBLIC_SENTRY_DSN is set (see .env.example / eas.json).
// We deliberately don't ship a placeholder DSN -- that would either silently
// point crash reports at nobody's project or, worse, at someone else's.
const DSN = process.env.EXPO_PUBLIC_SENTRY_DSN;

export const initCrashReporting = () => {
  if (!DSN) return;
  Sentry.init({
    dsn: DSN,
    tracesSampleRate: 0.2,
    enabled: !__DEV__,
  });
};

export { Sentry };
