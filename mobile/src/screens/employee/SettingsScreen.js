import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Switch,
  Alert,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";

import { Ionicons } from "@expo/vector-icons";

import ProfileHeader from "../../components/profile/ProfileHeader";
import { useAuth } from "../../store/AuthContext";
import {
  getBiometricLockEnabled, setBiometricLockEnabled,
  getNotificationsEnabled, setNotificationsEnabled,
} from "../../utils/preferences";
import {
  requestNotificationPermission, scheduleDailyCheckinReminder, cancelDailyCheckinReminder,
} from "../../utils/localNotifications";

export default function SettingsScreen({ navigation }) {
  const { signOut } = useAuth();
  const [notifications, setNotifications] = useState(true);
  const [biometric, setBiometric] = useState(true);

  useEffect(() => {
    (async () => {
      setBiometric(await getBiometricLockEnabled());
      setNotifications(await getNotificationsEnabled());
    })();
  }, []);

  const handleToggleNotifications = async (value) => {
    if (value) {
      const granted = await requestNotificationPermission();
      if (!granted) {
        Alert.alert(
          "Permission Needed",
          "Enable notifications for this app in your device settings to receive attendance reminders."
        );
        return;
      }
      await scheduleDailyCheckinReminder();
    } else {
      await cancelDailyCheckinReminder();
    }
    setNotifications(value);
    await setNotificationsEnabled(value);
  };

  const handleToggleBiometric = async (value) => {
    if (value) {
      const hasHw = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = hasHw && await LocalAuthentication.isEnrolledAsync();
      if (!isEnrolled) {
        Alert.alert(
          "Not Available",
          "No fingerprint or Face ID is enrolled on this device. Set it up in your device settings first."
        );
        return;
      }
    }
    setBiometric(value);
    await setBiometricLockEnabled(value);
  };

  const handleLogout = () => {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: signOut },
    ]);
  };

  const SettingItem = ({
    icon,
    title,
    subtitle,
    right,
    danger = false,
    onPress,
  }) => (
    <TouchableOpacity
      activeOpacity={0.8}
      style={styles.settingCard}
      onPress={onPress}
    >
      <View style={styles.leftSection}>
        <View
          style={[
            styles.iconContainer,
            danger && { backgroundColor: "#FEF2F2" },
          ]}
        >
          <Ionicons
            name={icon}
            size={22}
            color={danger ? "#DC2626" : "#173B8C"}
          />
        </View>

        <View style={{ flex: 1 }}>
          <Text
            style={[
              styles.title,
              danger && { color: "#DC2626" },
            ]}
          >
            {title}
          </Text>

          {subtitle ? (
            <Text style={styles.subtitle}>{subtitle}</Text>
          ) : null}
        </View>
      </View>

      {right}
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="Settings"
        showBack
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {/* Preferences */}

        <Text style={styles.sectionTitle}>
          Preferences
        </Text>

        <SettingItem
          icon="notifications-outline"
          title="Attendance Reminders"
          subtitle="Daily on-device check-in reminder"
          right={
            <Switch
              value={notifications}
              onValueChange={handleToggleNotifications}
              trackColor={{
                false: "#CBD5E1",
                true: "#173B8C",
              }}
            />
          }
        />

        <SettingItem
          icon="mail-outline"
          title="Email Alerts"
          subtitle="Coming soon"
          right={
            <Switch
              value={false}
              disabled
              trackColor={{
                false: "#CBD5E1",
                true: "#173B8C",
              }}
            />
          }
        />

        <SettingItem
          icon="moon-outline"
          title="Dark Mode"
          subtitle="Coming soon"
          right={
            <Switch
              value={false}
              disabled
              trackColor={{
                false: "#CBD5E1",
                true: "#173B8C",
              }}
            />
          }
        />

        <Text style={styles.sectionTitle}>
          Security
        </Text>

        <SettingItem
          icon="finger-print-outline"
          title="Biometric Login"
          subtitle="Use fingerprint or Face ID"
          right={
            <Switch
              value={biometric}
              onValueChange={handleToggleBiometric}
              trackColor={{
                false: "#CBD5E1",
                true: "#173B8C",
              }}
            />
          }
        />

        <SettingItem
          icon="lock-closed-outline"
          title="Change Password"
          subtitle="Update your account password"
          onPress={() => navigation.navigate("Security")}
          right={
            <Ionicons
              name="chevron-forward"
              size={20}
              color="#94A3B8"
            />
          }
        />

        <Text style={styles.sectionTitle}>
          About
        </Text>

        <SettingItem
          icon="information-circle-outline"
          title="About Application"
          subtitle="Version 1.0.0"
          onPress={() => Alert.alert("Employee Attendance", "Enterprise Workforce Platform\nVersion 1.0.0")}
          right={
            <Ionicons
              name="chevron-forward"
              size={20}
              color="#94A3B8"
            />
          }
        />

        <SettingItem
          icon="document-text-outline"
          title="Privacy Policy"
          subtitle="Read our privacy policy"
          onPress={() => navigation.navigate("Policies")}
          right={
            <Ionicons
              name="chevron-forward"
              size={20}
              color="#94A3B8"
            />
          }
        />

        <SettingItem
          icon="shield-checkmark-outline"
          title="Terms & Conditions"
          subtitle="View terms of service"
          onPress={() => navigation.navigate("Policies")}
          right={
            <Ionicons
              name="chevron-forward"
              size={20}
              color="#94A3B8"
            />
          }
        />

        <Text style={styles.sectionTitle}>
          Account
        </Text>

        <SettingItem
          icon="log-out-outline"
          title="Logout"
          subtitle="Sign out from this device"
          danger
          onPress={handleLogout}
          right={
            <Ionicons
              name="chevron-forward"
              size={20}
              color="#DC2626"
            />
          }
        />

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F8FAFC",
  },

  content: {
    paddingHorizontal: 18,
    paddingBottom: 40,
  },

  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 14,
    marginTop: 10,
  },

  settingCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",

    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 3,
    },
    elevation: 2,
  },

  leftSection: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },

  iconContainer: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },

  title: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },

  subtitle: {
    marginTop: 4,
    fontSize: 13,
    color: "#64748B",
    fontWeight: "500",
  },
});