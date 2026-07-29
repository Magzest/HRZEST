<<<<<<< HEAD
<<<<<<< HEAD
=======
<<<<<<< HEAD
import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";

import AdminDashboard from "../screens/admin/AdminDashboard";
import EmployeesScreen from "../screens/admin/EmployeesScreen";
import AttendanceScreen from "../screens/admin/AttendanceScreen";
import AnalyticsScreen from "../screens/admin/AnalyticsScreen";
import SettingsScreen from "../screens/admin/SettingsScreen";

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
          shadowOffset: {
            width: 0,
            height: -3,
          },

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
              icon = focused
                ? "calendar"
                : "calendar-outline";
              break;

            case "Analytics":
              icon = focused
                ? "bar-chart"
                : "bar-chart-outline";
              break;

            case "Settings":
              icon = focused
                ? "settings"
                : "settings-outline";
              break;

            default:
              icon = "ellipse";
          }

          return (
            <Ionicons
              name={icon}
              size={22}
              color={color}
            />
          );
        },
      })}
    >
      <Tab.Screen
        name="Dashboard"
        component={AdminDashboard}
        options={{
          tabBarLabel: "Home",
        }}
      />

      <Tab.Screen
        name="Employees"
        component={EmployeesScreen}
        options={{
          tabBarLabel: "Staff",
        }}
      />

      <Tab.Screen
        name="Attendance"
        component={AttendanceScreen}
        options={{
          tabBarLabel: "Attendance",
        }}
      />

      <Tab.Screen
        name="Analytics"
        component={AnalyticsScreen}
        options={{
          tabBarLabel: "Analytics",
        }}
      />

      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          tabBarLabel: "Settings",
        }}
      />
    </Tab.Navigator>
  );
=======
>>>>>>> 4ee786a7 (Add CompOff and Performance admin screens)
=======
>>>>>>> 6dbd917e (Update admin attendance and payroll screens)
import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { Ionicons } from "@expo/vector-icons";

import PayrollScreen from "../screens/admin/PayrollScreen";
import AdminDashboard from "../screens/admin/AdminDashboard";
import EmployeesScreen from "../screens/admin/EmployeesScreen";
import AttendanceScreen from "../screens/admin/AttendanceScreen";
import AnalyticsScreen from "../screens/admin/AnalyticsScreen";
import SettingsScreen from "../screens/admin/SettingsScreen";
<<<<<<< HEAD
=======
import CompOffScreen from "../screens/admin/CompOffScreen";
<<<<<<< HEAD
>>>>>>> 4ee786a7 (Add CompOff and Performance admin screens)
=======
import MarkAttendanceScreen from "../screens/admin/MarkAttendanceScreen";
import LeaveRequestsScreen from "../screens/admin/LeaveRequestsScreen";
>>>>>>> 6dbd917e (Update admin attendance and payroll screens)

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
            case "Analytics":
              icon = focused ? "bar-chart" : "bar-chart-outline";
              break;
            case "Settings":
              icon = focused ? "settings" : "settings-outline";
              break;
            default:
              icon = "ellipse";
          }

          return (
            <Ionicons
              name={icon}
              size={22}
              color={color}
            />
          );
        },
      })}
    >
      {/* ─────────────────────────────────────────────
          Visible quick-access tabs.
          These are a curated subset of the drawer
          items (Dashboard, Employees, Attendance,
          Analytics, Settings) — no duplication
          between the bottom bar and the drawer.
      ───────────────────────────────────────────── */}
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
        name="Analytics"
        component={AnalyticsScreen}
        options={{ tabBarLabel: "Analytics" }}
      />

      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{ tabBarLabel: "Settings" }}
      />

      {/* ─────────────────────────────────────────────
          Hidden screens — accessible only via the
          drawer so the bottom bar stays clean.
      ───────────────────────────────────────────── */}
      <Tab.Screen
        name="Payroll"
        component={PayrollScreen}
        options={{ tabBarButton: () => null }}
      />

      <Tab.Screen
<<<<<<< HEAD
  name="Payroll"
  component={SalaryPayslipsScreen}
  options={{
    tabBarButton: () => null,
  }}
/>
<<<<<<< HEAD
    </Tab.Navigator>
  );
=======
<Tab.Screen
  name="CompOff"
  component={CompOffScreen}
  options={{
    tabBarButton: () => null,
  }}
/>
    </Tab.Navigator>
  );
>>>>>>> 216f1b3 (Add CompOff and Performance admin screens)
>>>>>>> 4ee786a7 (Add CompOff and Performance admin screens)
}
=======
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
        name="LeaveRequests"
        component={LeaveRequestsScreen}
        options={{ tabBarButton: () => null }}
      />
    </Tab.Navigator>
  );
}
>>>>>>> 6dbd917e (Update admin attendance and payroll screens)
