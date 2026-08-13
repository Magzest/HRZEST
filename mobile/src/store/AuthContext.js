import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { adminLogout, employeeLogout } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]     = useState(null);   // { role:'admin'|'employee', name, employeeId? }
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const token = await AsyncStorage.getItem('token');
        const saved = await AsyncStorage.getItem('user');
        if (token && saved) {
          setUser(JSON.parse(saved));
        } else {
          await AsyncStorage.multiRemove(['token', 'user', 'user_role', 'user_id']);
          setUser(null);
        }
      } catch (_) {}
      setLoading(false);
    })();
  }, []);

  const signIn = async (token, userData) => {
    await AsyncStorage.setItem('token', token);
    await AsyncStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const signOut = async () => {
    try {
      if (user?.role === 'admin') {
        await adminLogout();
      } else if (user?.role === 'employee') {
        await employeeLogout();
      }
    } catch (_) {}
    await AsyncStorage.multiRemove(['token', 'user', 'user_role', 'user_id']);
    setUser(null);
  };

  const updateUser = async (partialData) => {
    setUser((prev) => {
      if (!prev) return partialData;
      const updated = { ...prev, ...partialData };
      AsyncStorage.setItem('user', JSON.stringify(updated)).catch(() => {});
      return updated;
    });
  };

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signOut, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
