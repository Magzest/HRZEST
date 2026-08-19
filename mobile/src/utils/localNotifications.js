import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

// This app has no push backend yet (registering an Expo push token and
// triggering sends from the server — e.g. on leave approval or an admin
// broadcast — needs a new backend endpoint, out of scope for a mobile-only
// change). What we CAN do without touching the backend is on-device local
// notifications: permission handling plus a daily attendance reminder.

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

const CHECKIN_REMINDER_ID = 'daily-checkin-reminder';

export const requestNotificationPermission = async () => {
  const { status: existing } = await Notifications.getPermissionsAsync();
  if (existing === 'granted') return true;
  const { status } = await Notifications.requestPermissionsAsync();
  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  return status === 'granted';
};

export const scheduleDailyCheckinReminder = async (hour = 9, minute = 30) => {
  await Notifications.cancelScheduledNotificationAsync(CHECKIN_REMINDER_ID).catch(() => {});
  await Notifications.scheduleNotificationAsync({
    identifier: CHECKIN_REMINDER_ID,
    content: {
      title: 'Attendance Reminder',
      body: "Don't forget to check in for today.",
    },
    trigger: { hour, minute, type: Notifications.SchedulableTriggerInputTypes.DAILY },
  });
};

export const cancelDailyCheckinReminder = () =>
  Notifications.cancelScheduledNotificationAsync(CHECKIN_REMINDER_ID).catch(() => {});
