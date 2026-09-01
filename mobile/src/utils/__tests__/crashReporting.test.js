jest.mock('@sentry/react-native', () => ({
  __esModule: true,
  init: jest.fn(),
}));

// initCrashReporting reads EXPO_PUBLIC_SENTRY_DSN and __DEV__ once, at
// module-load time, so each scenario needs its own resetModules() +
// re-require after setting up the environment.
describe('crashReporting', () => {
  const originalEnv = process.env.EXPO_PUBLIC_SENTRY_DSN;
  const originalDev = global.__DEV__;

  afterEach(() => {
    process.env.EXPO_PUBLIC_SENTRY_DSN = originalEnv;
    global.__DEV__ = originalDev;
    jest.clearAllMocks();
  });

  it('does not initialize Sentry when no DSN is configured', () => {
    jest.resetModules();
    delete process.env.EXPO_PUBLIC_SENTRY_DSN;
    const Sentry = require('@sentry/react-native');
    const { initCrashReporting } = require('../crashReporting');

    initCrashReporting();

    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('initializes Sentry with the configured DSN and a 0.2 trace sample rate', () => {
    jest.resetModules();
    process.env.EXPO_PUBLIC_SENTRY_DSN = 'https://example@sentry.io/123';
    global.__DEV__ = false;
    const Sentry = require('@sentry/react-native');
    const { initCrashReporting } = require('../crashReporting');

    initCrashReporting();

    expect(Sentry.init).toHaveBeenCalledWith({
      dsn: 'https://example@sentry.io/123',
      tracesSampleRate: 0.2,
      enabled: true,
    });
  });

  it('initializes with enabled:false while in dev, even with a DSN set', () => {
    jest.resetModules();
    process.env.EXPO_PUBLIC_SENTRY_DSN = 'https://example@sentry.io/123';
    global.__DEV__ = true;
    const Sentry = require('@sentry/react-native');
    const { initCrashReporting } = require('../crashReporting');

    initCrashReporting();

    expect(Sentry.init).toHaveBeenCalledWith(
      expect.objectContaining({ enabled: false })
    );
  });

  it('re-exports the Sentry module for callers that need it directly', () => {
    jest.resetModules();
    const Sentry = require('@sentry/react-native');
    const { Sentry: ReExportedSentry } = require('../crashReporting');

    expect(ReExportedSentry).toBe(Sentry);
  });
});
