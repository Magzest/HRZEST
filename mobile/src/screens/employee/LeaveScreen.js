import React, { useState, useCallback } from "react";
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  Alert, ActivityIndicator, TextInput,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import ProfileHeader from "../../components/profile/ProfileHeader";
import { useFocusEffect } from "@react-navigation/native";
import { submitLeaveRequest, fetchEmployeeLeaves, cancelLeaveRequest } from "../../api/client";

const REASONS = [
  { label: "Sick Leave",       value: "Sick Leave",       icon: "medical-outline" },
  { label: "Personal Work",    value: "Personal Work",    icon: "person-outline" },
  { label: "Family Emergency", value: "Family Emergency", icon: "people-outline" },
  { label: "Travel",           value: "Travel",           icon: "airplane-outline" },
  { label: "Planned Leave",    value: "Planned Leave",    icon: "calendar-outline" },
  { label: "Other",            value: null,               icon: "ellipsis-horizontal-outline" },
];

const STATUS_STYLE = {
  Approved: { bg: "#DCFCE7", text: "#166534" },
  Pending:  { bg: "#FEF9C3", text: "#854D0E" },
  Rejected: { bg: "#FEE2E2", text: "#991B1B" },
};

function addDays(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d;
}

function toISO(d) {
  return new Date(d).toISOString().split("T")[0];
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function LeaveScreen() {
  const [tab, setTab]         = useState("request");
  const [leaveDate, setDate]  = useState(toISO(addDays(1)));
  const [reason, setReason]   = useState("");
  const [custom, setCustom]   = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const [history, setHistory]       = useState(null);
  const [histLoading, setHistLoading] = useState(false);
  const [cancelling, setCancelling]   = useState(null);

  const loadHistory = async () => {
    setHistLoading(true);
    try {
      const res = await fetchEmployeeLeaves();
      if (res.data.ok) setHistory(res.data);
    } catch {
      Alert.alert("Error", "Failed to load leave history.");
    }
    setHistLoading(false);
  };

  useFocusEffect(useCallback(() => { loadHistory(); }, []));

  const handleCancel = (lid, leaveDate) => {
    Alert.alert(
      "Cancel Leave Request",
      `Cancel your leave request for ${fmtDate(leaveDate)}?`,
      [
        { text: "No", style: "cancel" },
        {
          text: "Yes, Cancel",
          style: "destructive",
          onPress: async () => {
            setCancelling(lid);
            try {
              const res = await cancelLeaveRequest(lid);
              if (res.data.ok) {
                loadHistory();
              } else {
                Alert.alert("Error", res.data.msg || "Could not cancel.");
              }
            } catch (e) {
              Alert.alert("Error", e.response?.data?.msg || "Failed to connect.");
            }
            setCancelling(null);
          },
        },
      ]
    );
  };

  const handleSubmit = async () => {
    const finalReason = reason === null ? custom.trim() : reason;
    if (!finalReason) { Alert.alert("Error", "Please select or enter a reason."); return; }
    Alert.alert("Submit Leave Request", `Date: ${leaveDate}\nReason: ${finalReason}\n\nSubmit this request?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Submit",
        onPress: async () => {
          setLoading(true);
          try {
            const res = await submitLeaveRequest(leaveDate, finalReason);
            if (res.data.ok) {
              setSuccess(true);
              setReason(""); setCustom("");
              setTimeout(() => setSuccess(false), 3000);
              loadHistory();
            } else {
              Alert.alert("Error", res.data.msg || "Failed to submit.");
            }
          } catch (e) {
            Alert.alert("Error", e.response?.data?.msg || "Failed to connect.");
          }
          setLoading(false);
        },
      },
    ]);
  };

  const dateOptions = Array.from({ length: 30 }, (_, i) => {
    const d = addDays(i + 1);
    return { iso: toISO(d), num: d.getDate(), mon: d.toLocaleString("default", { month: "short" }), day: d.toLocaleString("default", { weekday: "short" }) };
  });

  return (
    <LinearGradient colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]} style={styles.bg}>
      <ProfileHeader
  title="Leave Management"
  showBack={false}
/>

      {/* Tab bar */}
      <View style={styles.tabBar}>
        <TouchableOpacity style={[styles.tabBtn, tab === "request" && styles.tabBtnActive]} onPress={() => setTab("request")}>
          <Text style={[styles.tabTxt, tab === "request" && styles.tabTxtActive]}>Apply Leave</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.tabBtn, tab === "history" && styles.tabBtnActive]} onPress={() => setTab("history")}>
          <Text style={[styles.tabTxt, tab === "history" && styles.tabTxtActive]}>History</Text>
          {history?.summary?.pending > 0 && (
            <View style={styles.badge}><Text style={styles.badgeTxt}>{history.summary.pending}</Text></View>
          )}
        </TouchableOpacity>
      </View>

      {tab === "request" ? (
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          {success && (
            <View style={styles.successBanner}>
              <Ionicons name="checkmark-circle" size={18} color="#166534" />
              <Text style={styles.successTxt}>Leave request submitted successfully!</Text>
            </View>
          )}

          {/* Leave balance summary */}
          {history && (
            <View style={styles.balanceRow}>
              <View style={[styles.balCard, { backgroundColor: "#DCFCE7" }]}>
                <Text style={[styles.balNum, { color: "#166534" }]}>{history.summary.approved}</Text>
                <Text style={[styles.balLabel, { color: "#166534" }]}>Approved</Text>
              </View>
              <View style={[styles.balCard, { backgroundColor: "#FEF9C3" }]}>
                <Text style={[styles.balNum, { color: "#854D0E" }]}>{history.summary.pending}</Text>
                <Text style={[styles.balLabel, { color: "#854D0E" }]}>Pending</Text>
              </View>
              <View style={[styles.balCard, { backgroundColor: "#FEE2E2" }]}>
                <Text style={[styles.balNum, { color: "#991B1B" }]}>{history.summary.rejected}</Text>
                <Text style={[styles.balLabel, { color: "#991B1B" }]}>Rejected</Text>
              </View>
            </View>
          )}

          {/* Date picker */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Select Date</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              {dateOptions.map(opt => (
                <TouchableOpacity
                  key={opt.iso}
                  style={[styles.dateChip, leaveDate === opt.iso && styles.dateChipActive]}
                  onPress={() => setDate(opt.iso)}
                >
                  <Text style={[styles.dateDay, leaveDate === opt.iso && styles.dateDayActive]}>{opt.day}</Text>
                  <Text style={[styles.dateNum, leaveDate === opt.iso && styles.dateNumActive]}>{opt.num}</Text>
                  <Text style={[styles.dateMon, leaveDate === opt.iso && styles.dateMonActive]}>{opt.mon}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <Text style={styles.selectedDate}>
              <Ionicons name="calendar-outline" size={13} color="#94A3B8" /> {fmtDate(leaveDate)}
            </Text>
          </View>

          {/* Reason */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Reason</Text>
            <View style={styles.chips}>
              {REASONS.map(r => (
                <TouchableOpacity
                  key={r.label}
                  style={[styles.chip, reason === r.value && styles.chipActive]}
                  onPress={() => { setReason(r.value); setCustom(""); }}
                >
                  <Ionicons name={r.icon} size={14} color={reason === r.value ? "#FFFFFF" : "#64748B"} />
                  <Text style={[styles.chipTxt, reason === r.value && styles.chipTxtActive]}>{r.label}</Text>
                </TouchableOpacity>
              ))}
            </View>
            {reason === null && (
              <TextInput
                style={styles.textarea}
                placeholder="Describe your reason..."
                placeholderTextColor="#94A3B8"
                multiline
                numberOfLines={3}
                value={custom}
                onChangeText={setCustom}
              />
            )}
          </View>

          <TouchableOpacity style={[styles.submitBtn, loading && { opacity: 0.6 }]} onPress={handleSubmit} disabled={loading}>
            {loading ? <ActivityIndicator color="#fff" /> : (
              <>
                <Ionicons name="paper-plane-outline" size={18} color="#FFFFFF" />
                <Text style={styles.submitTxt}>Submit Leave Request</Text>
              </>
            )}
          </TouchableOpacity>
          <View style={{ height: 40 }} />
        </ScrollView>
      ) : (
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          {histLoading ? (
            <View style={styles.center}><ActivityIndicator size="large" color="#173B8C" /></View>
          ) : !history || history.leaves.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="document-text-outline" size={48} color="#CBD5E1" />
              <Text style={styles.emptyTxt}>No leave requests yet</Text>
            </View>
          ) : (
            <>
              {/* Summary stats */}
              <View style={styles.balanceRow}>
                <View style={[styles.balCard, { backgroundColor: "#DCFCE7" }]}>
                  <Text style={[styles.balNum, { color: "#166534" }]}>{history.summary.approved}</Text>
                  <Text style={[styles.balLabel, { color: "#166534" }]}>Approved</Text>
                </View>
                <View style={[styles.balCard, { backgroundColor: "#FEF9C3" }]}>
                  <Text style={[styles.balNum, { color: "#854D0E" }]}>{history.summary.pending}</Text>
                  <Text style={[styles.balLabel, { color: "#854D0E" }]}>Pending</Text>
                </View>
                <View style={[styles.balCard, { backgroundColor: "#FEE2E2" }]}>
                  <Text style={[styles.balNum, { color: "#991B1B" }]}>{history.summary.rejected}</Text>
                  <Text style={[styles.balLabel, { color: "#991B1B" }]}>Rejected</Text>
                </View>
              </View>

              {history.leaves.map(l => {
                const st = STATUS_STYLE[l.status] || STATUS_STYLE.Pending;
                const isFuture = new Date(l.leave_date) > new Date();
                return (
                  <View key={l.id} style={styles.leaveRow}>
                    <View style={styles.leaveDateBox}>
                      <Text style={styles.leaveDateNum}>{new Date(l.leave_date).getDate()}</Text>
                      <Text style={styles.leaveDateMon}>
                        {new Date(l.leave_date).toLocaleString("default", { month: "short" })}
                      </Text>
                    </View>
                    <View style={styles.leaveInfo}>
                      <Text style={styles.leaveReason}>{l.reason}</Text>
                      <Text style={styles.leaveSubmitted}>Submitted {fmtDate(l.created_at)}</Text>
                    </View>
                    <View style={{ alignItems: "flex-end", gap: 6 }}>
                      <View style={[styles.statusBadge, { backgroundColor: st.bg }]}>
                        <Text style={[styles.statusTxt, { color: st.text }]}>{l.status}</Text>
                      </View>
                      {l.status === "Pending" && isFuture && (
                        <TouchableOpacity
                          onPress={() => handleCancel(l.id, l.leave_date)}
                          disabled={cancelling === l.id}
                          style={styles.cancelBtn}
                        >
                          <Text style={styles.cancelBtnTxt}>
                            {cancelling === l.id ? "…" : "Cancel"}
                          </Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                );
              })}
            </>
          )}
          <View style={{ height: 110 }} />
        </ScrollView>
      )}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  bg:     { flex: 1 },
  header: { flexDirection: "row", alignItems: "center", paddingTop: 55, paddingHorizontal: 20, paddingBottom: 14, backgroundColor: "#FFFFFF", shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
  headerTitle: { fontSize: 16, fontWeight: "700", color: "#0F172A", marginLeft: 10 },
  tabBar:  { flexDirection: "row", backgroundColor: "#FFFFFF", paddingHorizontal: 20, paddingBottom: 0, borderBottomWidth: 1, borderColor: "#E2E8F0" },
  tabBtn:  { flex: 1, paddingVertical: 14, alignItems: "center", flexDirection: "row", justifyContent: "center" },
  tabBtnActive: { borderBottomWidth: 2, borderColor: "#173B8C" },
  tabTxt:  { fontSize: 13, fontWeight: "600", color: "#94A3B8" },
  tabTxtActive: { color: "#173B8C" },
  badge:   { backgroundColor: "#EF4444", borderRadius: 10, minWidth: 18, height: 18, justifyContent: "center", alignItems: "center", marginLeft: 6, paddingHorizontal: 4 },
  badgeTxt:{ color: "#FFF", fontSize: 10, fontWeight: "700" },
  scroll:  { padding: 20 },
  center:  { alignItems: "center", paddingVertical: 60 },
  successBanner: { flexDirection: "row", alignItems: "center", backgroundColor: "#DCFCE7", borderRadius: 12, padding: 14, marginBottom: 16 },
  successTxt:    { color: "#166534", fontWeight: "600", marginLeft: 8 },
  balanceRow:  { flexDirection: "row", justifyContent: "space-between", marginBottom: 16 },
  balCard:     { flex: 1, marginHorizontal: 4, borderRadius: 14, padding: 12, alignItems: "center" },
  balNum:      { fontSize: 18, fontWeight: "800" },
  balLabel:    { fontSize: 11, fontWeight: "600", marginTop: 2 },
  card:      { backgroundColor: "#FFFFFF", borderRadius: 18, padding: 18, marginBottom: 14, shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  cardTitle: { fontSize: 13, fontWeight: "700", color: "#0F172A", marginBottom: 14 },
  dateChip:       { width: 58, alignItems: "center", padding: 10, borderRadius: 14, marginRight: 8, backgroundColor: "#F1F5F9", borderWidth: 1.5, borderColor: "#E2E8F0" },
  dateChipActive: { backgroundColor: "#173B8C", borderColor: "#173B8C" },
  dateDay:        { fontSize: 10, color: "#94A3B8", fontWeight: "600", marginBottom: 2 },
  dateDayActive:  { color: "rgba(255,255,255,0.8)" },
  dateNum:        { fontSize: 15, fontWeight: "800", color: "#0F172A" },
  dateNumActive:  { color: "#FFFFFF" },
  dateMon:        { fontSize: 10, color: "#94A3B8", marginTop: 2 },
  dateMonActive:  { color: "rgba(255,255,255,0.8)" },
  selectedDate:   { color: "#94A3B8", fontSize: 12, marginTop: 10 },
  chips:     { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip:      { flexDirection: "row", alignItems: "center", paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, backgroundColor: "#F1F5F9", borderWidth: 1.5, borderColor: "#E2E8F0", gap: 6 },
  chipActive:    { backgroundColor: "#173B8C", borderColor: "#173B8C" },
  chipTxt:       { color: "#64748B", fontSize: 12, fontWeight: "600" },
  chipTxtActive: { color: "#FFFFFF" },
  textarea: { marginTop: 12, borderWidth: 1.5, borderColor: "#E2E8F0", borderRadius: 12, padding: 12, fontSize: 13, color: "#0F172A", minHeight: 80, textAlignVertical: "top" },
  submitBtn: { backgroundColor: "#173B8C", paddingVertical: 14, borderRadius: 16, alignItems: "center", flexDirection: "row", justifyContent: "center", gap: 8, marginTop: 4 },
  submitTxt: { color: "#fff", fontWeight: "700", fontSize: 13 },
  empty:     { alignItems: "center", paddingVertical: 50 },
  emptyTxt:  { color: "#94A3B8", fontSize: 13, marginTop: 12 },
  leaveRow:  { flexDirection: "row", alignItems: "center", backgroundColor: "#FFFFFF", borderRadius: 16, padding: 14, marginBottom: 10, shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 }, elevation: 2 },
  leaveDateBox: { width: 48, height: 52, borderRadius: 14, backgroundColor: "#EEF4FF", alignItems: "center", justifyContent: "center", marginRight: 14 },
  leaveDateNum: { fontSize: 15, fontWeight: "800", color: "#173B8C" },
  leaveDateMon: { fontSize: 10, fontWeight: "600", color: "#173B8C" },
  leaveInfo:    { flex: 1 },
  leaveReason:  { fontSize: 13, fontWeight: "700", color: "#0F172A" },
  leaveSubmitted:{ fontSize: 12, color: "#94A3B8", marginTop: 2 },
  statusBadge:  { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 20 },
  statusTxt:    { fontSize: 11, fontWeight: "700" },
  cancelBtn:    { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20, backgroundColor: "#FEE2E2", borderWidth: 1, borderColor: "#FECACA" },
  cancelBtnTxt: { fontSize: 11, fontWeight: "700", color: "#DC2626" },
});
