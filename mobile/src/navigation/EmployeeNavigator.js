import React, { useState } from "react";
import { View } from "react-native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
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
import PerformanceScreen from "../screens/employee/PerformanceScreen";
import OnboardingScreen from "../screens/employee/OnboardingScreen";
import ProfileNavigator from "./ProfileNavigator";
import PoliciesScreen from "../screens/employee/PoliciesScreen";
import ResignScreen from "../screens/employee/ResignScreen";

const Tab = createBottomTabNavigator();

export default function EmployeeNavigator() {
  const [showScanner, setShowScanner] = useState(false);

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
            height: 72,
            backgroundColor: "#173B8C",
            borderTopWidth: 0,
            borderTopLeftRadius: 26,
            borderTopRightRadius: 26,
            elevation: 15,
            shadowColor: "#000",
            shadowOpacity: 0.12,
            shadowRadius: 20,
            shadowOffset: { width: 0, height: -3 },
            paddingTop: 8,
            paddingBottom: 8,
          },
          tabBarLabelStyle: {
            fontSize: 10,
            fontWeight: "600",
            marginTop: 2,
          },
          tabBarActiveTintColor: "#FFFFFF",
          tabBarInactiveTintColor: "rgba(255,255,255,0.72)",
          tabBarIcon: ({ focused, color }) => {
            if (route.name === "Home") {
              return <Ionicons name={focused ? "home" : "home-outline"} size={22} color={color} />;
            }
            if (route.name === "Leave") {
              return <Ionicons name={focused ? "document-text" : "document-text-outline"} size={22} color={color} />;
            }
            if (route.name === "Tickets") {
              return <Ionicons name={focused ? "ticket" : "ticket-outline"} size={22} color={color} />;
            }
            if (route.name === "Notifications") {
              return <Ionicons name={focused ? "notifications" : "notifications-outline"} size={22} color={color} />;
            }
            return <Ionicons name="ellipse" size={22} color={color} />;
          },
        })}
      >
        {/* 5 Visible Bottom Bar Items */}
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
            tabBarItemStyle: { top: 3 },
            tabBarIcon: () => (
              <View
                style={{
                  width: 62,
                  height: 62,
                  borderRadius: 31,
                  backgroundColor: "#22C55E",
                  justifyContent: "center",
                  alignItems: "center",
                  borderWidth: 3,
                  borderColor: "#FFFFFF",
                  elevation: 10,
                }}
              >
                <Ionicons name="qr-code" size={28} color="#FFFFFF" />
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

        {/* Hidden Screens - Accessible via Drawer Menu */}
        <Tab.Screen
          name="Attendance"
          component={AttendanceScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="CompOff"
          component={CompOffScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Holidays"
          component={HolidaysScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Earnings"
          component={EarningsScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Performance"
          component={PerformanceScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Onboarding"
          component={OnboardingScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Profile"
          component={ProfileNavigator}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Policies"
          component={PoliciesScreen}
          options={{ tabBarButton: () => null }}
        />

        <Tab.Screen
          name="Resignation"
          component={ResignScreen}
          options={{ tabBarButton: () => null }}
        />
      </Tab.Navigator>
    </>
  );
}