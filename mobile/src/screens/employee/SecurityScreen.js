import React, { useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  Switch,
  Alert,
} from "react-native";
import * as LocalAuthentication from "expo-local-authentication";

import { Ionicons } from "@expo/vector-icons";

import ProfileHeader from "../../components/profile/ProfileHeader";
import SaveButton from "../../components/profile/SaveButton";
import { changePassword } from "../../api/client";
import { getBiometricLockEnabled, setBiometricLockEnabled } from "../../utils/preferences";

export default function SecurityScreen() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [biometric, setBiometric] = useState(true);

  useEffect(() => {
    getBiometricLockEnabled().then(setBiometric);
  }, []);

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

  const handleUpdateSecurity = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      Alert.alert("Input Required", "Please fill in all password fields.");
      return;
    }
    if (newPassword !== confirmPassword) {
      Alert.alert("Mismatch", "New password and confirmation don't match.");
      return;
    }
    if (newPassword.length < 6) {
      Alert.alert("Too Short", "New password must be at least 6 characters.");
      return;
    }
    setSaving(true);
    try {
      const res = await changePassword(currentPassword, newPassword);
      if (res?.data?.ok) {
        Alert.alert("Password Changed", "Your password has been updated successfully.");
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        Alert.alert("Failed", res?.data?.msg || "Could not change password.");
      }
    } catch (e) {
      Alert.alert("Failed", e?.response?.data?.msg || "Could not change password.");
    }
    setSaving(false);
  };

  const PasswordInput = ({
    label,
    value,
    onChangeText,
    secure,
    onToggle,
  }) => (
    <View style={styles.inputContainer}>
      <Text style={styles.label}>{label}</Text>

      <View style={styles.inputWrapper}>
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={label}
          secureTextEntry={!secure}
          style={styles.input}
          placeholderTextColor="#94A3B8"
        />

        <TouchableOpacity onPress={onToggle}>
          <Ionicons
            name={secure ? "eye-outline" : "eye-off-outline"}
            size={22}
            color="#64748B"
          />
        </TouchableOpacity>
      </View>
    </View>
  );

  const SecurityOption = ({
    icon,
    title,
    subtitle,
    value,
    onValueChange,
  }) => (
    <View style={styles.optionCard}>
      <View style={styles.leftSection}>
        <View style={styles.iconContainer}>
          <Ionicons
            name={icon}
            size={22}
            color="#173B8C"
          />
        </View>

        <View style={{ flex: 1 }}>
          <Text style={styles.optionTitle}>{title}</Text>
          <Text style={styles.optionSubtitle}>
            {subtitle}
          </Text>
        </View>
      </View>

      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{
          false: "#CBD5E1",
          true: "#173B8C",
        }}
      />
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="Security"
        showBack
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        <Text style={styles.sectionTitle}>
          Change Password
        </Text>

        <PasswordInput
          label="Current Password"
          value={currentPassword}
          onChangeText={setCurrentPassword}
          secure={showCurrent}
          onToggle={() => setShowCurrent(!showCurrent)}
        />

        <PasswordInput
          label="New Password"
          value={newPassword}
          onChangeText={setNewPassword}
          secure={showNew}
          onToggle={() => setShowNew(!showNew)}
        />

        <PasswordInput
          label="Confirm Password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          secure={showConfirm}
          onToggle={() => setShowConfirm(!showConfirm)}
        />

        <Text style={styles.sectionTitle}>
          Security Settings
        </Text>

        <SecurityOption
          icon="finger-print-outline"
          title="Biometric Authentication"
          subtitle="Unlock the app using fingerprint or Face ID"
          value={biometric}
          onValueChange={handleToggleBiometric}
        />

        <SaveButton
          title="Update Password"
          onPress={handleUpdateSecurity}
          loading={saving}
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
    paddingBottom: 120,
  },

  sectionTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 16,
    marginTop: 12,
  },

  inputContainer: {
    marginBottom: 18,
  },

  label: {
    fontSize: 14,
    fontWeight: "700",
    color: "#334155",
    marginBottom: 8,
  },

  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#FFFFFF",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    paddingHorizontal: 16,
    height: 56,
  },

  input: {
    flex: 1,
    fontSize: 15,
    color: "#0F172A",
  },

  optionCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",

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

  optionTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },

  optionSubtitle: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 4,
  },

  activityCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    padding: 16,
    borderWidth: 1,
    borderColor: "#E8EDF3",
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 28,

    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 3,
    },
    elevation: 2,
  },

  activityIcon: {
    width: 50,
    height: 50,
    borderRadius: 14,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 14,
  },

  activityTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: "#0F172A",
  },

  activitySubtitle: {
    marginTop: 4,
    fontSize: 13,
    color: "#64748B",
  },

  activityTime: {
    marginTop: 6,
    fontSize: 12,
    color: "#16A34A",
    fontWeight: "600",
  },
});