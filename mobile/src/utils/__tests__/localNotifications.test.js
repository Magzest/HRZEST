jest.mock('expo-notifications', () => ({
  __esModule: true,
  setNotificationHandler: jest.fn(),
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  setNotificationChannelAsync: jest.fn(),
  cancelScheduledNotificationAsync: jest.fn(),
  scheduleNotificationAsync: jest.fn(),
  AndroidImportance: { DEFAULT: 3 },
  SchedulableTriggerInputTypes: { DAILY: 'daily' },
}));

const Notifications = require('expo-notifications');
const { Platform } = require('react-native');
const {
  requestNotificationPermission,
  scheduleDailyCheckinReminder,
  cancelDailyCheckinReminder,
} = require('../localNotifications');

describe('localNotifications', () => {
  const originalPlatformOS = Platform.OS;

  afterEach(() => {
    jest.clearAllMocks();
    Platform.OS = originalPlatformOS;
  });

  // requestNotificationPermission reads Platform.OS at call time (not at
  // module load), so switching it per-test is just a property assignment --
  // no module reset/re-require needed (and re-requiring here would in fact
  // break things, since jest.mock factories re-run on reset and produce a
  // second, disconnected set of mock fns that this file's `Notifications`
  // reference would no longer point at).
  describe('requestNotificationPermission on iOS', () => {
    beforeEach(() => {
      Platform.OS = 'ios';
    });

    it('short-circuits to true without prompting if permission is already granted', async () => {
      Notifications.getPermissionsAsync.mockResolvedValue({ status: 'granted' });

      const result = await requestNotificationPermission();

      expect(result).toBe(true);
      expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
    });

    it('prompts for permission when not already granted, and does not set up an android channel', async () => {
      Notifications.getPermissionsAsync.mockResolvedValue({ status: 'undetermined' });
      Notifications.requestPermissionsAsync.mockResolvedValue({ status: 'granted' });

      const result = await requestNotificationPermission();

      expect(result).toBe(true);
      expect(Notifications.requestPermissionsAsync).toHaveBeenCalled();
      expect(Notifications.setNotificationChannelAsync).not.toHaveBeenCalled();
    });

    it('returns false when the user denies the prompt', async () => {
      Notifications.getPermissionsAsync.mockResolvedValue({ status: 'undetermined' });
      Notifications.requestPermissionsAsync.mockResolvedValue({ status: 'denied' });

      const result = await requestNotificationPermission();

      expect(result).toBe(false);
    });
  });

  describe('requestNotificationPermission on Android', () => {
    beforeEach(() => {
      Platform.OS = 'android';
    });

    it('sets up the default notification channel after prompting', async () => {
      Notifications.getPermissionsAsync.mockResolvedValue({ status: 'undetermined' });
      Notifications.requestPermissionsAsync.mockResolvedValue({ status: 'granted' });

      await requestNotificationPermission();

      expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
        'default',
        expect.objectContaining({ name: 'default', importance: Notifications.AndroidImportance.DEFAULT })
      );
    });
  });

  describe('scheduleDailyCheckinReminder / cancelDailyCheckinReminder', () => {
    it('cancels any existing reminder before scheduling a new one', async () => {
      Notifications.cancelScheduledNotificationAsync.mockResolvedValue();
      Notifications.scheduleNotificationAsync.mockResolvedValue();

      await scheduleDailyCheckinReminder(8, 15);

      expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('daily-checkin-reminder');
      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          identifier: 'daily-checkin-reminder',
          trigger: { hour: 8, minute: 15, type: 'daily' },
        })
      );
    });

    it('defaults to 9:30 when no time is given', async () => {
      Notifications.cancelScheduledNotificationAsync.mockResolvedValue();
      Notifications.scheduleNotificationAsync.mockResolvedValue();

      await scheduleDailyCheckinReminder();

      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({ trigger: { hour: 9, minute: 30, type: 'daily' } })
      );
    });

    it('does not blow up scheduling if there was nothing to cancel', async () => {
      Notifications.cancelScheduledNotificationAsync.mockRejectedValue(new Error('nothing scheduled'));
      Notifications.scheduleNotificationAsync.mockResolvedValue();

      await expect(scheduleDailyCheckinReminder()).resolves.toBeUndefined();
      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalled();
    });

    it('cancelDailyCheckinReminder swallows a cancellation error instead of rejecting', async () => {
      Notifications.cancelScheduledNotificationAsync.mockRejectedValue(new Error('nothing scheduled'));

      await expect(cancelDailyCheckinReminder()).resolves.toBeUndefined();
      expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('daily-checkin-reminder');
    });
  });
});
