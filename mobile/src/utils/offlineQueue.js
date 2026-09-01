import AsyncStorage from '@react-native-async-storage/async-storage';

const QUEUE_KEY = 'offline_punch_queue';

export async function queuePunch(lat = null, lon = null) {
  const punch = {
    id: `${Date.now().toString()}-${Math.random().toString(36).slice(2)}`,
    punched_at: new Date().toISOString(),
    lat,
    lon,
  };
  const raw   = await AsyncStorage.getItem(QUEUE_KEY);
  const queue = raw ? JSON.parse(raw) : [];
  queue.push(punch);
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  return punch;
}

export async function getPendingPunches() {
  const raw = await AsyncStorage.getItem(QUEUE_KEY);
  return raw ? JSON.parse(raw) : [];
}

export async function clearQueue() {
  await AsyncStorage.removeItem(QUEUE_KEY);
}

export async function removeFromQueue(id) {
  const raw   = await AsyncStorage.getItem(QUEUE_KEY);
  const queue = (raw ? JSON.parse(raw) : []).filter(p => p.id !== id);
  await AsyncStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
}
