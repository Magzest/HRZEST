import React, { useState } from "react";
import { View, StyleSheet } from "react-native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";

import AttendanceScannerModal from "../screens/AttendanceScannerModal";
import EmployeeDashboard from "../screens/employee/EmployeeDashboard";
import LeaveScreen from "../screens/employee/LeaveScreen";
import TicketsScreen from "../screens/employee/TicketsScreen";
import NotificationsScreen from "../screens/NotificationsScreen";

import AttendanceScreen from "../screens/employee/AttendanceScreen";
import CompOffScreen from "../screens/employee/CompOffScreen";
import HolidaysScreen from "../screens/employee/HolidaysScreen";
import EarningsScreen from "../screens/employee/EarningsScreen";
import PayslipsScreen from "../screens/employee/PayslipsScreen";
import PerformanceScreen from "../screens/employee/PerformanceScreen";
import OnboardingScreen from "../screens/employee/OnboardingScreen";
import ProfileScreen from "../screens/employee/ProfileScreen";
import PersonalInfoScreen from "../screens/employee/PersonalInfoScreen";
import WorkInfoScreen from "../screens/employee/WorkInfoScreen";
import ContactScreen from "../screens/employee/ContactScreen";
import EmergencyContactScreen from "../screens/employee/EmergencyContactScreen";
import EducationScreen from "../screens/employee/EducationScreen";
import ExperienceScreen from "../screens/employee/ExperienceScreen";
import DocumentsScreen from "../screens/employee/DocumentsScreen";
import BankDetailsScreen from "../screens/employee/BankDetailsScreen";
import SecurityScreen from "../screens/employee/SecurityScreen";
import SettingsScreen from "../screens/employee/SettingsScreen";
import PoliciesScreen from "../screens/employee/PoliciesScreen";
import ResignScreen from "../screens/employee/ResignScreen";

const Tab = createBottomTabNavigator();

export default function EmployeeNavigator() {
  const [showScanner, setShowScanner] = useState(false);
  const insets = useSafeAreaInsets();
  const bottomInset = Math.max(insets.bottom, 16);

  return (
    <>
      <AttendanceScannerModal
        visible={showScanner}
        onClose={() => setShowScanner(false)}
        onSuccess={() => setShowScanner(false)}
      />

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
          tabBarItemStyle: {
            justifyContent: "center",
            alignItems: "center",
            height: 52,
          },
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: "600",
            letterSpacing: 0.2,
            marginTop: 1,
          },
          tabBarActiveTintColor: "#FFFFFF",
          tabBarInactiveTintColor: "rgba(255, 255, 255, 0.65)",
          tabBarIcon: ({ focused, color }) => {
            let iconName = "ellipse";
            if (route.name === "Home") {
              iconName = focused ? "home" : "home-outline";
            } else if (route.name === "Leave") {
              iconName = focused ? "calendar" : "calendar-outline";
            } else if (route.name === "Tickets") {
              iconName = focused ? "chatbubbles" : "chatbubbles-outline";
            } else if (route.name === "Notifications") {
              iconName = focused ? "notifications" : "notifications-outline";
            }
            return (
              <View style={styles.iconContainer}>
                <Ionicons name={iconName} size={22} color={color} />
                {focused && <View style={styles.activeDot} />}
              </View>
            );
          },
        })}
      >
        {/* 5 Main Tabs */}
        <Tab.Screen
          name="Home"
          component={EmployeeDashboard}
          options={{ tabBarLabel: "Home" }}
        />

        <Tab.Screen
          name="Leave"
          component={LeaveScreen}
          options={{ tabBarLabel: "Leave" }}
        />

        <Tab.Screen
          name="Scan"
          component={View}
          listeners={{
            tabPress: (e) => {
              e.preventDefault();
              setShowScanner(true);
            },
          }}
          options={{
            tabBarLabel: "",
            tabBarIcon: () => (
              <View style={styles.scanButton}>
                <Ionicons name="qr-code" size={29} color="#FFFFFF" />
              </View>
            ),
          }}
        />

        <Tab.Screen
          name="Tickets"
          component={TicketsScreen}
          options={{ tabBarLabel: "Tickets" }}
        />

        <Tab.Screen
          name="Notifications"
          component={NotificationsScreen}
          options={{ tabBarLabel: "Alerts" }}
        />

        {/* Hidden Drawer & Profile Screens */}
        <Tab.Screen
          name="Attendance"
          component={AttendanceScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="CompOff"
          component={CompOffScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Holidays"
          component={HolidaysScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Earnings"
          component={EarningsScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Payslips"
          component={PayslipsScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Performance"
          component={PerformanceScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Onboarding"
          component={OnboardingScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Profile"
          component={ProfileScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="PersonalInfo"
          component={PersonalInfoScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="WorkInfo"
          component={WorkInfoScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Contact"
          component={ContactScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="EmergencyContact"
          component={EmergencyContactScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Education"
          component={EducationScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Experience"
          component={ExperienceScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Documents"
          component={DocumentsScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="BankDetails"
          component={BankDetailsScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Security"
          component={SecurityScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Settings"
          component={SettingsScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Policies"
          component={PoliciesScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />

        <Tab.Screen
          name="Resignation"
          component={ResignScreen}
          options={{ tabBarItemStyle: { display: "none" } }}
        />
      </Tab.Navigator>
    </>
  );
}

const styles = StyleSheet.create({
  iconContainer: {
    alignItems: "center",
    justifyContent: "center",
    height: 26,
  },
  activeDot: {
    width: 4,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#FFFFFF",
    position: "absolute",
    bottom: -4,
  },
  scanButton: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#22C55E",
    justifyContent: "center",
    alignItems: "center",
    top: -10,
    borderWidth: 3.5,
    borderColor: "#FFFFFF",
    elevation: 14,
    shadowColor: "#22C55E",
    shadowOpacity: 0.45,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
});