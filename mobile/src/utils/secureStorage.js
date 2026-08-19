import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import AsyncStorage from '@react-native-async-storage/async-storage';

// SecureStore has no web implementation (no Keychain/Keystore in a browser),
// so session data falls back to AsyncStorage there. Native builds (the ones
// that actually ship to app stores) always get encrypted storage.
const isWeb = Platform.OS === 'web';

export const secureGetItem = (key) =>
  isWeb ? AsyncStorage.getItem(key) : SecureStore.getItemAsync(key);

export const secureSetItem = (key, value) =>
  isWeb ? AsyncStorage.setItem(key, value) : SecureStore.setItemAsync(key, value);

export const secureRemoveItem = (key) =>
  isWeb ? AsyncStorage.removeItem(key) : SecureStore.deleteItemAsync(key);

export const secureMultiRemove = async (keys) => {
  await Promise.all(keys.map((key) => secureRemoveItem(key).catch(() => {})));
};
