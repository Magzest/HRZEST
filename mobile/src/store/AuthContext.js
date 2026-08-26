import React, { createContext, useContext, useState, useEffect } from 'react';
import * as LocalAuthentication from 'expo-local-authentication';

import { adminLogout, employeeLogout, setUnauthorizedHandler } from '../api/client';
import { secureGetItem, secureSetItem, secureMultiRemove } from '../utils/secureStorage';
import { getBiometricLockEnabled } from '../utils/preferences';

const AuthContext = createContext(null);

const SESSION_KEYS = ['token', 'user', 'user_role', 'user_id'];

export function AuthProvider({ children }) {
  const [user, setUser]     = useState(null);   // { role:'admin'|'employee', adminRole:'admin'|'hr' (only set when role==='admin'), name, employeeId? }
  const [loading, setLoading] = useState(true);
  // App-lock: a session restored from disk on cold start is gated behind a
  // biometric prompt (when the device has one enrolled) before its data is
  // shown, same as banking/enterprise apps. A fresh signIn() never locks --
  // the user just proved identity with a password.
  const [locked, setLocked] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const token = await secureGetItem('token');
        const saved = await secureGetItem('user');
        if (token && saved) {
          const restoredUser = JSON.parse(saved);
          setUser(restoredUser);
          try {
            const wantsLock = await getBiometricLockEnabled();
            const hasHw = wantsLock && await LocalAuthentication.hasHardwareAsync();
            const isEnrolled = hasHw && await LocalAuthentication.isEnrolledAsync();
            if (isEnrolled) setLocked(true);
          } catch (_) {}
        } else {
          await secureMultiRemove(SESSION_KEYS);
          setUser(null);
        }
      } catch (_) {}
      setLoading(false);
    })();

    // Any 401 from the API (expired/revoked token) clears the session and
    // drops the user back on the login screen instead of leaving them
    // stuck retrying calls with a dead token.
    setUnauthorizedHandler(() => {
      secureMultiRemove(SESSION_KEYS).catch(() => {});
      setUser(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const signIn = async (token, userData) => {
    await secureSetItem('token', token);
    await secureSetItem('user', JSON.stringify(userData));
    setUser(userData);
    setLocked(false);
  };

  const signOut = async () => {
    try {
      if (user?.role === 'admin') {
        await adminLogout();
      } else if (user?.role === 'employee') {
        await employeeLogout();
      }
    } catch (_) {}
    await secureMultiRemove(SESSION_KEYS);
    setUser(null);
    setLocked(false);
  };

  const unlockApp = async () => {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'Unlock HRzest',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false, // allow device PIN/pattern as a fallback
      });
      if (result.success) {
        setLocked(false);
        return true;
      }
    } catch (_) {}
    return false;
  };

  const updateUser = async (partialData) => {
    setUser((prev) => {
      if (!prev) return partialData;
      const updated = { ...prev, ...partialData };
      secureSetItem('user', JSON.stringify(updated)).catch(() => {});
      return updated;
    });
  };

  return (
    <AuthContext.Provider value={{ user, loading, locked, signIn, signOut, updateUser, unlockApp }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
