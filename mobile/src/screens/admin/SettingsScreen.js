import React from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  Switch,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";

import AdminHeader from "../../components/admin/AdminHeader";
import THEME from "../../constants/theme";

export default function SettingsScreen({ navigation }) {
  const [geofenceEnabled, setGeofenceEnabled] = React.useState(true);
  const [pushNotifs, setPushNotifs] = React.useState(true);
  const [faceRecog, setFaceRecog] = React.useState(true);

  const renderSettingItem = (icon, title, subtitle, rightElement) => {
    return (
      <View style={styles.settingItem} key={title}>
        <View style={styles.settingLeft}>
          <View style={styles.iconContainer}>
            <Ionicons name={icon} size={20} color="#173B8C" />
          </View>

          <View style={styles.settingContent}>
            <Text style={styles.settingTitle}>{title}</Text>
            <Text style={styles.settingSubtitle}>{subtitle}</Text>
          </View>
        </View>

        {rightElement || (
          <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
        )}
      </View>
    );
  };

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader
          title="System Settings"
          onMenu={() => navigation.dispatch(DrawerActions.openDrawer())}
        />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
        >
          {/* Admin Profile Summary */}
          <View style={styles.profileCard}>
            <View style={styles.avatar}>
              <Ionicons name="shield-checkmark" size={36} color="#173B8C" />
            </View>
            <Text style={styles.name}>Administrator</Text>
            <Text style={styles.email}>admin@company.com</Text>
            <View style={styles.roleBadge}>
              <Text style={styles.roleText}>Super Administrator</Text>
            </View>
          </View>

          {/* Attendance & GPS Settings */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>ATTENDANCE & GPS</Text>

            {renderSettingItem(
              "location-outline",
              "GPS Geofencing",
              "Restrict check-in within office coordinates",
              <Switch
                value={geofenceEnabled}
                onValueChange={setGeofenceEnabled}
                trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                thumbColor={geofenceEnabled ? "#173B8C" : "#F1F5F9"}
              />
            )}

            {renderSettingItem(
              "scan-outline",
              "Face Recognition Verification",
              "Require photo match on check-in",
              <Switch
                value={faceRecog}
                onValueChange={setFaceRecog}
                trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                thumbColor={faceRecog ? "#173B8C" : "#F1F5F9"}
              />
            )}

            {renderSettingItem(
              "time-outline",
              "Office Hours & Shifts",
              "Standard shift 09:00 AM - 06:00 PM"
            )}
          </View>

          {/* Security & System */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>SECURITY & SYSTEM</Text>

            {renderSettingItem(
              "notifications-outline",
              "Push Notifications",
              "Security alerts & pending requests",
              <Switch
                value={pushNotifs}
                onValueChange={setPushNotifs}
                trackColor={{ false: "#CBD5E1", true: "#93C5FD" }}
                thumbColor={pushNotifs ? "#173B8C" : "#F1F5F9"}
              />
            )}

            {renderSettingItem(
              "key-outline",
              "Encryption & Secrets",
              "Fernet PII encryption enabled"
            )}

            {renderSettingItem(
              "business-outline",
              "Company Details",
              "HR Management System Inc."
            )}
          </View>

          {/* App Info */}
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>ABOUT</Text>
            {renderSettingItem(
              "information-circle-outline",
              "App Version",
              "SaaS Mobile Edition v1.0.0"
            )}
          </View>

          <View style={{ height: 110 }} />
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  profileCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 20,
    alignItems: "center",
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    elevation: 3,
  },
  avatar: {
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 12,
  },
  name: { fontSize: 20, fontWeight: "800", color: "#0F172A" },
  email: { fontSize: 13, color: "#64748B", marginTop: 2 },
  roleBadge: {
    marginTop: 10,
    backgroundColor: "#EEF4FF",
    paddingHorizontal: 14,
    paddingVertical: 4,
    borderRadius: 16,
  },
  roleText: { color: "#173B8C", fontSize: 12, fontWeight: "700" },
  sectionCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "#E2E8F0",
    marginBottom: 14,
    overflow: "hidden",
    elevation: 2,
  },
  sectionTitle: {
    paddingHorizontal: 18,
    paddingTop: 16,
    paddingBottom: 10,
    fontSize: 11,
    fontWeight: "800",
    color: "#94A3B8",
    letterSpacing: 1,
  },
  settingItem: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: "#F1F5F9",
  },
  settingLeft: { flexDirection: "row", alignItems: "center", flex: 1 },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#EEF4FF",
    justifyContent: "center",
    alignItems: "center",
  },
  settingContent: { flex: 1, marginLeft: 14 },
  settingTitle: { fontSize: 15, color: "#0F172A", fontWeight: "700" },
  settingSubtitle: { marginTop: 2, fontSize: 12, color: "#64748B" },
});