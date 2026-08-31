import React, { useState } from "react";
import { View, ActivityIndicator } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { StatusBar } from "expo-status-bar";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { AuthProvider, useAuth } from "./src/store/AuthContext";
import { ThemeProvider } from "./src/store/ThemeContext";
import LaunchCountdownScreen from "./src/screens/LaunchCountdownScreen";
import LoginScreen from "./src/screens/LoginScreen";
import AppLockScreen from "./src/screens/AppLockScreen";
import AdminDrawerNavigator from "./src/navigation/AdminDrawerNavigator";
import EmployeeDrawerNavigator from "./src/navigation/EmployeeDrawerNavigator";
import { initCrashReporting } from "./src/utils/crashReporting";

initCrashReporting();

function RootNavigator() {
  const { user, loading, locked } = useAuth();
  const [showLaunch, setShowLaunch] = useState(true);

  if (loading) {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: "#0F172A",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <ActivityIndicator size="large" color="#FFFFFF" />
      </View>
    );
  }

  if (!user) {
    if (showLaunch) {
      return (
        <LaunchCountdownScreen
          onContinue={() => setShowLaunch(false)}
        />
      );
    }
    return <LoginScreen />;
  }

  if (locked) {
    return <AppLockScreen />;
  }

  if (user.role === "admin") {
    return <AdminDrawerNavigator />;
  }

  if (user.role === "employee") {
    return <EmployeeDrawerNavigator />;
  }

  return <LoginScreen />;
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <ThemeProvider>
        <AuthProvider>
          <NavigationContainer>
            <StatusBar style="light" />
            <RootNavigator />
          </NavigationContainer>
        </AuthProvider>
      </ThemeProvider>
    </GestureHandlerRootView>
  );
}
