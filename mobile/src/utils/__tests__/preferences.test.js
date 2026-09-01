import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  getBiometricLockEnabled,
  setBiometricLockEnabled,
  getNotificationsEnabled,
  setNotificationsEnabled,
  getDarkModeEnabled,
  setDarkModeEnabled,
} from '../preferences';

describe('preferences', () => {
  beforeEach(async () => {
    await AsyncStorage.clear();
  });

  describe('biometric lock (opt-out, defaults true)', () => {
    it('defaults to true when nothing has been stored', async () => {
      expect(await getBiometricLockEnabled()).toBe(true);
    });

    it('persists an explicit true', async () => {
      await setBiometricLockEnabled(true);
      expect(await getBiometricLockEnabled()).toBe(true);
      expect(await AsyncStorage.getItem('@pref_biometric_lock_enabled')).toBe('true');
    });

    it('persists an explicit false', async () => {
      await setBiometricLockEnabled(false);
      expect(await getBiometricLockEnabled()).toBe(false);
      expect(await AsyncStorage.getItem('@pref_biometric_lock_enabled')).toBe('false');
    });
  });

  describe('notifications (opt-out, defaults true)', () => {
    it('defaults to true when nothing has been stored', async () => {
      expect(await getNotificationsEnabled()).toBe(true);
    });

    it('persists false after being disabled', async () => {
      await setNotificationsEnabled(false);
      expect(await getNotificationsEnabled()).toBe(false);
    });

    it('persists true after being explicitly enabled again', async () => {
      await setNotificationsEnabled(false);
      await setNotificationsEnabled(true);
      expect(await getNotificationsEnabled()).toBe(true);
    });
  });

  describe('dark mode (opt-in, defaults false)', () => {
    it('defaults to false when nothing has been stored', async () => {
      expect(await getDarkModeEnabled()).toBe(false);
    });

    it('persists true after being enabled', async () => {
      await setDarkModeEnabled(true);
      expect(await getDarkModeEnabled()).toBe(true);
      expect(await AsyncStorage.getItem('@pref_dark_mode_enabled')).toBe('true');
    });

    it('persists false after being explicitly disabled again', async () => {
      await setDarkModeEnabled(true);
      await setDarkModeEnabled(false);
      expect(await getDarkModeEnabled()).toBe(false);
    });
  });

  it('keeps the three preference keys independent of each other', async () => {
    await setBiometricLockEnabled(false);
    await setNotificationsEnabled(false);
    await setDarkModeEnabled(true);

    expect(await getBiometricLockEnabled()).toBe(false);
    expect(await getNotificationsEnabled()).toBe(false);
    expect(await getDarkModeEnabled()).toBe(true);
  });
});
