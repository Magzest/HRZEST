import React, { useCallback, useEffect, useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
  Modal,
  TextInput,
  Alert,
  Switch,
} from "react-native";
import { DrawerActions } from "@react-navigation/native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import THEME from "../../constants/theme";
import AdminHeader from "../../components/admin/AdminHeader";
import { fetchHrAccounts, createHrAccount, setHrAccountStatus } from "../../api/client";

// Admin-only (mirrors web's role_required("admin") on /hr_accounts) --
// creating/disabling HR user accounts had zero mobile UI before this,
// forcing admins to switch to the web dashboard for it.
export default function HrAccountsScreen({ navigation }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [togglingUsername, setTogglingUsername] = useState(null);

  const [addModalVisible, setAddModalVisible] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetchHrAccounts();
      setAccounts(res?.data?.ok && Array.isArray(res.data.accounts) ? res.data.accounts : []);
    } catch (e) {
      setAccounts([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const handleToggleActive = (account) => {
    const nextActive = !account.is_active;
    Alert.alert(
      nextActive ? "Activate Account" : "Terminate Account",
      `${nextActive ? "Activate" : "Terminate"} HR account '${account.username}'?`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: nextActive ? "Activate" : "Terminate",
          style: nextActive ? "default" : "destructive",
          onPress: async () => {
            setTogglingUsername(account.username);
            let res;
            try {
              res = await setHrAccountStatus(account.username, nextActive);
            } catch (e) {
              res = e?.response;
            }
            setTogglingUsername(null);
            if (!res?.data?.ok) {
              Alert.alert("Action Failed", res?.data?.msg || "Could not update this account.");
              return;
            }
            setAccounts((prev) => prev.map((a) => (a.username === account.username ? { ...a, is_active: nextActive } : a)));
          },
        },
      ]
    );
  };

  const handleCreate = async () => {
    const usernameTrim = newUsername.trim();
    if (!usernameTrim) {
      Alert.alert("Input Required", "Username is required.");
      return;
    }
    if (newPassword.length < 8) {
      Alert.alert("Input Required", "Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    let res;
    try {
      res = await createHrAccount(usernameTrim, newEmail.trim(), newPassword);
    } catch (e) {
      res = e?.response;
    }
    setSubmitting(false);
    if (!res?.data?.ok) {
      Alert.alert("Creation Failed", res?.data?.msg || "Could not create this HR account.");
      return;
    }
    setAddModalVisible(false);
    setNewUsername("");
    setNewEmail("");
    setNewPassword("");
    Alert.alert("Created", `HR account '${usernameTrim}' created.`);
    load();
  };

  return (
    <LinearGradient colors={["#F8FAFC", "#F1F5F9", "#E2E8F0"]} style={styles.container}>
      <SafeAreaView style={{ flex: 1 }}>
        <AdminHeader title="HR Accounts" onMenu={() => navigation.dispatch(DrawerActions.openDrawer())} />

        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.content}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[THEME.colors.primary]} />}
        >
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>HR Team Accounts ({accounts.length})</Text>
            <TouchableOpacity style={styles.addBtn} onPress={() => setAddModalVisible(true)}>
              <Ionicons name="add" size={18} color="#FFFFFF" />
              <Text style={styles.addBtnText}>Add HR</Text>
            </TouchableOpacity>
          </View>

          {loading ? (
            <ActivityIndicator size="large" color="#173B8C" style={{ marginTop: 24 }} />
          ) : accounts.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="people-outline" size={44} color="#94A3B8" />
              <Text style={styles.emptyTitle}>No HR Accounts Yet</Text>
              <Text style={styles.emptySub}>Add an HR account to let someone else manage employees for you.</Text>
            </View>
          ) : (
            accounts.map((acc) => (
              <View key={acc.username} style={styles.card}>
                <View style={styles.cardRow}>
                  <View style={styles.avatar}>
                    <Text style={styles.avatarText}>{acc.username.charAt(0).toUpperCase()}</Text>
                  </View>
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text style={styles.username}>{acc.username}</Text>
                    <Text style={styles.email}>{acc.email || "No email set"}</Text>
                  </View>
                  {togglingUsername === acc.username ? (
                    <ActivityIndicator size="small" color="#173B8C" />
                  ) : (
                    <Switch
                      value={acc.is_active}
                      onValueChange={() => handleToggleActive(acc)}
                      trackColor={{ false: "#E2E8F0", true: "#86EFAC" }}
                      thumbColor={acc.is_active ? "#16A34A" : "#94A3B8"}
                    />
                  )}
                </View>
                <Text style={styles.created}>Created {acc.created_at ? acc.created_at.split(" ")[0] : "--"}</Text>
              </View>
            ))
          )}

          <View style={{ height: 100 }} />
        </ScrollView>

        {/* Add HR Account Modal */}
        <Modal visible={addModalVisible} transparent animationType="slide" onRequestClose={() => setAddModalVisible(false)}>
          <View style={{ flex: 1, backgroundColor: "rgba(15, 23, 42, 0.8)", justifyContent: "flex-end" }}>
            <View style={{ backgroundColor: "#FFFFFF", borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 20 }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 14, paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: "#F1F5F9" }}>
                <Text style={{ fontSize: 18, fontWeight: "800", color: "#0F172A" }}>Add HR Account</Text>
                <TouchableOpacity onPress={() => setAddModalVisible(false)}>
                  <Ionicons name="close-circle" size={26} color="#64748B" />
                </TouchableOpacity>
              </View>

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 4 }}>USERNAME *</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="hr.jane"
                value={newUsername}
                onChangeText={setNewUsername}
                autoCapitalize="none"
              />

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>EMAIL</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                placeholder="jane@company.com"
                value={newEmail}
                onChangeText={setNewEmail}
                keyboardType="email-address"
                autoCapitalize="none"
              />

              <Text style={{ fontSize: 11, fontWeight: "700", color: "#64748B", marginTop: 10 }}>PASSWORD * (MIN 8 CHARS)</Text>
              <TextInput
                style={{ backgroundColor: "#F8FAFC", borderWidth: 1, borderColor: "#E2E8F0", borderRadius: 10, padding: 10, marginTop: 4 }}
                value={newPassword}
                onChangeText={setNewPassword}
                secureTextEntry
              />

              <TouchableOpacity
                style={{ backgroundColor: "#173B8C", borderRadius: 14, paddingVertical: 14, alignItems: "center", marginTop: 20, marginBottom: 10 }}
                onPress={handleCreate}
                disabled={submitting}
              >
                {submitting ? <ActivityIndicator color="#FFFFFF" /> : <Text style={{ color: "#FFFFFF", fontWeight: "800", fontSize: 14 }}>Create Account</Text>}
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { paddingHorizontal: 20, paddingTop: 10 },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 14 },
  sectionTitle: { fontSize: 15, fontWeight: "800", color: "#0F172A" },
  addBtn: { flexDirection: "row", alignItems: "center", backgroundColor: "#173B8C", paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  addBtnText: { color: "#FFFFFF", fontWeight: "700", fontSize: 12, marginLeft: 4 },
  emptyCard: { backgroundColor: "#FFFFFF", borderRadius: 20, padding: 32, alignItems: "center", borderWidth: 1, borderColor: "#E2E8F0" },
  emptyTitle: { fontSize: 15, fontWeight: "700", color: "#334155", marginTop: 10 },
  emptySub: { fontSize: 12, color: "#64748B", textAlign: "center", marginTop: 4 },
  card: { backgroundColor: "#FFFFFF", borderRadius: 18, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: "#E2E8F0" },
  cardRow: { flexDirection: "row", alignItems: "center" },
  avatar: { width: 42, height: 42, borderRadius: 21, backgroundColor: "#EEF4FF", justifyContent: "center", alignItems: "center" },
  avatarText: { fontSize: 15, fontWeight: "800", color: "#173B8C" },
  username: { fontSize: 14, fontWeight: "700", color: "#0F172A" },
  email: { fontSize: 12, color: "#64748B", marginTop: 2 },
  created: { fontSize: 11, color: "#94A3B8", marginTop: 10 },
});
