import React from "react";
import { createStackNavigator } from "@react-navigation/stack";

import ProfileScreen from "../screens/employee/ProfileScreen";
import IdCardScreen from "../screens/IdCardScreen";
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

const Stack = createStackNavigator();

export default function ProfileNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen
        name="ProfileHome"
        component={ProfileScreen}
      />

      <Stack.Screen
        name="IdCard"
        component={IdCardScreen}
      />

      <Stack.Screen
        name="PersonalInfo"
        component={PersonalInfoScreen}
      />

      <Stack.Screen
        name="WorkInfo"
        component={WorkInfoScreen}
      />

      <Stack.Screen
        name="Contact"
        component={ContactScreen}
      />

      <Stack.Screen
        name="EmergencyContact"
        component={EmergencyContactScreen}
      />

      <Stack.Screen
        name="Education"
        component={EducationScreen}
      />

      <Stack.Screen
        name="Experience"
        component={ExperienceScreen}
      />

      <Stack.Screen
        name="Documents"
        component={DocumentsScreen}
      />

      <Stack.Screen
        name="BankDetails"
        component={BankDetailsScreen}
      />

      <Stack.Screen
        name="Security"
        component={SecurityScreen}
      />

      <Stack.Screen
        name="Settings"
        component={SettingsScreen}
      />
    </Stack.Navigator>
  );
}