// ─────────────────────────────────────────────────────────────
//  API_BASE_URL — set this before building a release APK/IPA.
//
//  PRODUCTION:
//    export const API_BASE_URL = 'https://yourdomain.com';
//
//  LOCAL DEV — USB debugging (adb reverse tcp:5000 tcp:5000):
//    export const API_BASE_URL = 'http://localhost:5000';
//
//  LOCAL DEV — real Android device on same Wi-Fi:
//    export const API_BASE_URL = 'http://192.168.1.x:5000';
//
//  SECURITY: Never ship a build pointing at http:// — Bearer
//  tokens are visible to anyone on the same network.
// ─────────────────────────────────────────────────────────────

import { Platform } from 'react-native';
import Constants from 'expo-constants';

const getDevHost = () => {
  try {
    const hostUri = Constants.expoConfig?.hostUri || Constants.manifest?.debuggerHost || Constants.manifest2?.extra?.expoGo?.developer?.tool;
    if (hostUri) {
      const ip = hostUri.split(':')[0];
      if (ip && ip !== 'localhost' && ip !== '127.0.0.1') {
        return ip;
      }
    }
  } catch (_) {}
  return Platform.OS === 'android' ? '10.0.2.2' : 'localhost';
};

const DEV_HOST = getDevHost();
export const API_BASE_URL = `http://${DEV_HOST}:5000`;

export const COLORS = {
  // Backgrounds
  adminBg:    ['#0f2027', '#203a43', '#2c5364'],
  employeeBg: ['#1a1a2e', '#16213e', '#0f3460'],
  purpleBg:   ['#667eea', '#764ba2'],

  // Cards / surfaces
  card:       'rgba(255,255,255,0.08)',
  cardHover:  'rgba(255,255,255,0.13)',
  sidebar:    'rgba(0,0,0,0.30)',
  border:     'rgba(255,255,255,0.12)',
  input:      'rgba(255,255,255,0.15)',

  // Text
  text:       '#ffffff',
  textMuted:  'rgba(255,255,255,0.60)',
  textDim:    'rgba(255,255,255,0.45)',

  // Accents
  blue:       '#3b82f6',
  blueLight:  '#93c5fd',
  green:      '#22c55e',
  greenLight: '#6ee56e',
  red:        '#ef4444',
  redLight:   '#fca5a5',
  yellow:     '#fbbf24',
  yellowLight:'#ffd166',
  purple:     '#8b5cf6',

  // Status badges (bg / text)
  pendingBg:  'rgba(251,191,36,0.18)',
  pendingTxt: '#ffd166',
  approvedBg: 'rgba(34,197,94,0.18)',
  approvedTxt:'#6ee56e',
  declinedBg: 'rgba(239,68,68,0.18)',
  declinedTxt:'#ff7e7e',
};
