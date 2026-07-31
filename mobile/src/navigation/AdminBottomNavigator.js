import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";

import AdminDashboard from "../screens/admin/AdminDashboard";
import EmployeesScreen from "../screens/admin/EmployeesScreen";
import AttendanceScreen from "../screens/admin/AttendanceScreen";
import LeaveRequestsScreen from "../screens/admin/LeaveRequestsScreen";
import SettingsScreen from "../screens/admin/SettingsScreen";

import SalaryPayslipsScreen from "../screens/admin/SalaryPayslipsScreen";
import AnalyticsScreen from "../screens/admin/AnalyticsScreen";
import CompOffScreen from "../screens/admin/CompOffScreen";
import MarkAttendanceScreen from "../screens/admin/MarkAttendanceScreen";
import ResignationsScreen from "../screens/admin/ResignationsScreen";
import AdminTicketsScreen from "../screens/admin/AdminTicketsScreen";
import PerformanceScreen from "../screens/admin/PerformanceScreen";
import OnboardingScreen from "../screens/admin/OnboardingScreen";
import OrgChartScreen from "../screens/admin/OrgChartScreen";
import DepartmentsScreen from "../screens/admin/DepartmentsScreen";

const Tab = createBottomTabNavigator();

export default function AdminBottomNavigator() {
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

        tabBarActiveTintColor: "#FFFFFF",
        tabBarInactiveTintColor: "rgba(255,255,255,0.72)",

        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: "600",
          marginTop: 2,
        },

        tabBarIcon: ({ focused, color }) => {
          let icon;

          switch (route.name) {
            case "Dashboard":
              icon = focused ? "home" : "home-outline";
              break;
            case "Employees":
              icon = focused ? "people" : "people-outline";
              break;
            case "Attendance":
              icon = focused ? "calendar" : "calendar-outline";
              break;
            case "LeaveRequests":
              icon = focused ? "checkmark-done-circle" : "checkmark-done-circle-outline";
              break;
            case "Settings":
              icon = focused ? "settings" : "settings-outline";
              break;
            default:
              icon = "ellipse";
          }

          return <Ionicons name={icon} size={22} color={color} />;
        },
      })}
    >
      {/* 5 Daily Quick-Access Tabs */}
      <Tab.Screen
        name="Dashboard"
        component={AdminDashboard}
        options={{ tabBarLabel: "Home" }}
      />

      <Tab.Screen
        name="Employees"
        component={EmployeesScreen}
        options={{ tabBarLabel: "Staff" }}
      />

      <Tab.Screen
        name="Attendance"
        component={AttendanceScreen}
        options={{ tabBarLabel: "Attendance" }}
      />

      <Tab.Screen
        name="LeaveRequests"
        component={LeaveRequestsScreen}
        options={{ tabBarLabel: "Approvals" }}
      />

      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ tabBarLabel: "Settings" }}
      />

      {/* Hidden Screens - Accessible via Drawer Menu */}
      <Tab.Screen
        name="Payroll"
        component={SalaryPayslipsScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
        name="Analytics"
        component={AnalyticsScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
        name="CompOff"
        component={CompOffScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
        name="MarkAttendance"
        component={MarkAttendanceScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
        name="Resignations"
        component={ResignationsScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
        name="Tickets"
        component={AdminTicketsScreen}
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
        name="OrgChart"
        component={OrgChartScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
        name="Departments"
        component={DepartmentsScreen}
        options={{ tabBarButton: () => null }}
      />
    </Tab.Navigator>
  );
}
