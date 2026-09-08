// secureStorage picks its backend (AsyncStorage on web, expo-secure-store
// on native) once, at module-load time, based on Platform.OS -- so each
// branch has to be exercised in its own resetModules() sandbox with
// Platform.OS mocked before the module is (re)required.

describe('secureStorage on native (Platform.OS !== "web")', () => {
  let secureGetItem, secureSetItem, secureRemoveItem, secureMultiRemove;
  let SecureStore;
  let AsyncStorage;

  beforeEach(() => {
    jest.resetModules();
    // secureStorage.js reads Platform.OS once at module-load time -- mutate
    // it on the real react-native module (rather than replacing the whole
    // module with jest.doMock, which strips out the NativeModules/
    // TurboModuleRegistry wiring jest-expo's native-module mocks depend on)
    // before requiring secureStorage fresh.
    require('react-native').Platform.OS = 'ios';
    SecureStore = require('expo-secure-store');
    AsyncStorage = require('@react-native-async-storage/async-storage');
    jest.spyOn(SecureStore, 'getItemAsync').mockResolvedValue('the-token');
    jest.spyOn(SecureStore, 'setItemAsync').mockResolvedValue();
    jest.spyOn(SecureStore, 'deleteItemAsync').mockResolvedValue();
    jest.spyOn(AsyncStorage, 'getItem');
    jest.spyOn(AsyncStorage, 'setItem');
    jest.spyOn(AsyncStorage, 'removeItem');
    ({ secureGetItem, secureSetItem, secureRemoveItem, secureMultiRemove } = require('../secureStorage'));
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('reads through expo-secure-store, not AsyncStorage', async () => {
    const value = await secureGetItem('token');
    expect(value).toBe('the-token');
    expect(SecureStore.getItemAsync).toHaveBeenCalledWith('token');
    expect(AsyncStorage.getItem).not.toHaveBeenCalled();
  });

  it('writes through expo-secure-store', async () => {
    await secureSetItem('token', 'abc123');
    expect(SecureStore.setItemAsync).toHaveBeenCalledWith('token', 'abc123');
    expect(AsyncStorage.setItem).not.toHaveBeenCalled();
  });

  it('removes through expo-secure-store', async () => {
    await secureRemoveItem('token');
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('token');
    expect(AsyncStorage.removeItem).not.toHaveBeenCalled();
  });

  it('secureMultiRemove removes every key given', async () => {
    await secureMultiRemove(['token', 'refresh']);
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('token');
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith('refresh');
  });

  it('secureMultiRemove swallows a per-key failure instead of rejecting', async () => {
    SecureStore.deleteItemAsync.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce();
    await expect(secureMultiRemove(['bad-key', 'good-key'])).resolves.toBeUndefined();
    expect(SecureStore.deleteItemAsync).toHaveBeenCalledTimes(2);
  });
});

describe('secureStorage on web (Platform.OS === "web")', () => {
  let secureGetItem, secureSetItem, secureRemoveItem, secureMultiRemove;
  let SecureStore;
  let AsyncStorage;

  beforeEach(() => {
    jest.resetModules();
    require('react-native').Platform.OS = 'web';
    SecureStore = require('expo-secure-store');
    AsyncStorage = require('@react-native-async-storage/async-storage');
    jest.spyOn(SecureStore, 'getItemAsync');
    jest.spyOn(SecureStore, 'setItemAsync');
    jest.spyOn(SecureStore, 'deleteItemAsync');
    jest.spyOn(AsyncStorage, 'getItem').mockResolvedValue('web-token');
    jest.spyOn(AsyncStorage, 'setItem').mockResolvedValue();
    jest.spyOn(AsyncStorage, 'removeItem').mockResolvedValue();
    ({ secureGetItem, secureSetItem, secureRemoveItem, secureMultiRemove } = require('../secureStorage'));
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('reads through AsyncStorage, not expo-secure-store', async () => {
    const value = await secureGetItem('token');
    expect(value).toBe('web-token');
    expect(AsyncStorage.getItem).toHaveBeenCalledWith('token');
    expect(SecureStore.getItemAsync).not.toHaveBeenCalled();
  });

  it('writes through AsyncStorage', async () => {
    await secureSetItem('token', 'xyz789');
    expect(AsyncStorage.setItem).toHaveBeenCalledWith('token', 'xyz789');
    expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
  });

  it('removes through AsyncStorage', async () => {
    await secureRemoveItem('token');
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('token');
    expect(SecureStore.deleteItemAsync).not.toHaveBeenCalled();
  });

  it('secureMultiRemove removes every key given', async () => {
    await secureMultiRemove(['token', 'refresh']);
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('token');
    expect(AsyncStorage.removeItem).toHaveBeenCalledWith('refresh');
  });

  it('secureMultiRemove swallows a per-key failure instead of rejecting', async () => {
    AsyncStorage.removeItem.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce();
    await expect(secureMultiRemove(['bad-key', 'good-key'])).resolves.toBeUndefined();
    expect(AsyncStorage.removeItem).toHaveBeenCalledTimes(2);
  });
});
