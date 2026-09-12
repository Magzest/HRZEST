import React from "react";
import { View, StyleSheet } from "react-native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import ManagerDashboard from "../screens/manager/ManagerDashboard";
// Reused directly from the admin screen set -- same data/API
// (fetchLeaveRequests/leaveAction, fetchResignations/resignationAction),
// same server-side role gate (_LEAVE_APPROVER_ROLES includes "manager"
// already), so there is nothing manager-specific to build into these
// screens themselves, only into which navigator mounts them.
import LeaveRequestsScreen from "../screens/admin/LeaveRequestsScreen";
import ResignationsScreen from "../screens/admin/ResignationsScreen";
import CompOffScreen from "../screens/admin/CompOffScreen";
import SettingsScreen from "../screens/admin/SettingsScreen";

const Tab = createBottomTabNavigator();

export default function ManagerBottomNavigator() {
  const insets = useSafeAreaInsets();
  const bottomInset = Math.max(insets.bottom, 16);

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarHideOnKeyboard: true,
        tabBarStyle: {
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 58 + bottomInset,
          backgroundColor: "#0B2253",
          borderTopWidth: 1,
          borderTopColor: "rgba(255, 255, 255, 0.15)",
          borderTopLeftRadius: 22,
          borderTopRightRadius: 22,
          elevation: 25,
          shadowColor: "#000",
          shadowOpacity: 0.3,
          shadowRadius: 16,
          shadowOffset: { width: 0, height: -4 },
          paddingTop: 6,
          paddingBottom: bottomInset,
        },
        tabBarItemStyle: { justifyContent: "center", alignItems: "center", height: 52 },
        tabBarActiveTintColor: "#FFFFFF",
        tabBarInactiveTintColor: "rgba(255, 255, 255, 0.65)",
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600", letterSpacing: 0.2, marginTop: 1 },
        tabBarIcon: ({ focused, color }) => {
          let icon;
          switch (route.name) {
            case "Dashboard":
              icon = focused ? "home" : "home-outline";
              break;
            case "LeaveRequests":
              icon = focused ? "checkmark-done-circle" : "checkmark-done-circle-outline";
              break;
            case "Resignations":
              icon = focused ? "exit" : "exit-outline";
              break;
            case "CompOff":
              icon = focused ? "time" : "time-outline";
              break;
            case "Settings":
              icon = focused ? "settings" : "settings-outline";
              break;
            default:
              icon = "ellipse";
          }
          return (
            <View style={styles.iconContainer}>
              <Ionicons name={icon} size={22} color={color} />
              {focused && <View style={styles.activeDot} />}
            </View>
          );
        },
      })}
    >
      <Tab.Screen name="Dashboard" component={ManagerDashboard} options={{ tabBarLabel: "Home" }} />
      <Tab.Screen name="LeaveRequests" component={LeaveRequestsScreen} options={{ tabBarLabel: "Leave" }} />
      <Tab.Screen name="Resignations" component={ResignationsScreen} options={{ tabBarLabel: "Resign" }} />
      <Tab.Screen name="CompOff" component={CompOffScreen} options={{ tabBarLabel: "OT" }} />
      <Tab.Screen name="Settings" component={SettingsScreen} options={{ tabBarLabel: "Settings" }} />
    </Tab.Navigator>
  );
}

const styles = StyleSheet.create({
  iconContainer: { alignItems: "center", justifyContent: "center", height: 26 },
  activeDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#FFFFFF",
    position: "absolute",
    bottom: -4,
  },
});
