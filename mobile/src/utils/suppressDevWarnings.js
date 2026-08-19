import { LogBox } from 'react-native';

// expo-notifications auto-registers a push-token listener the moment it's
// imported anywhere in the app (a side effect inside the package itself),
// which throws a loud console.error -- a full-screen red box on Android --
// in Expo Go specifically, because Expo Go dropped remote-push support in
// SDK 53. This app never uses remote push (only on-device local reminders,
// which work fine in Expo Go despite the warning), so it's a false alarm.
//
// This must be the FIRST import in index.js: ES modules evaluate imports
// in the order they're written, depth-first, before the importing file's
// own body runs -- so being import #1 guarantees this rule exists before
// anything else (including expo-notifications, several imports deep in
// App.js) gets a chance to load.
LogBox.ignoreLogs([
  'expo-notifications: Android Push notifications',
]);
