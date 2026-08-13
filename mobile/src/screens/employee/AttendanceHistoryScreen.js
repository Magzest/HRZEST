import React, { useState, useEffect } from "react";
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Alert,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { fetchEmployeeAttendance } from "../../api/client";

const TYPE_COLOR = {
  "Full Day":        { bg: "#DCFCE7", text: "#166534" },
  "Late - Full Day": { bg: "#FEF9C3", text: "#854D0E" },
  "Half Day":        { bg: "#FEF3C7", text: "#92400E" },
  "Late - Half Day": { bg: "#FEF3C7", text: "#92400E" },
};

const STATUS_COLOR = {
  "Full Day Login": "#22C55E",
  "Late Login":     "#F59E0B",
  "Half Day Login": "#F97316",
};

function fmtMinutes(mins) {
  if (!mins) return "--";
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}h ${m.toString().padStart(2, "0")}m`;
}

function MonthPicker({ year, month, onChange }) {
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const prev = () => {
    if (month === 1) onChange(year - 1, 12);
    else onChange(year, month - 1);
  };
  const next = () => {
    const now = new Date();
    if (year > now.getFullYear() || (year === now.getFullYear() && month >= now.getMonth() + 1)) return;
    if (month === 12) onChange(year + 1, 1);
    else onChange(year, month + 1);
  };
  return (
    <View style={mp.row}>
      <TouchableOpacity onPress={prev} style={mp.btn}>
        <Ionicons name="chevron-back" size={20} color="#173B8C" />
      </TouchableOpacity>
      <Text style={mp.label}>{MONTHS[month - 1]} {year}</Text>
      <TouchableOpacity onPress={next} style={mp.btn}>
        <Ionicons name="chevron-forward" size={20} color="#173B8C" />
      </TouchableOpacity>
    </View>
  );
}

const mp = StyleSheet.create({
  row:   { flexDirection: "row", alignItems: "center", justifyContent: "center", marginBottom: 20 },
  btn:   { width: 36, height: 36, borderRadius: 10, backgroundColor: "#EEF4FF", justifyContent: "center", alignItems: "center" },
  label: { width: 130, textAlign: "center", fontSize: 17, fontWeight: "700", color: "#0F172A" },
});

export default function AttendanceHistoryScreen({ navigation }) {
  const now = new Date();
  const [year, setYear]     = useState(now.getFullYear());
  const [month, setMonth]   = useState(now.getMonth() + 1);
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async (y, m) => {
    setLoading(true);
    try {
      const res = await fetchEmployeeAttendance(y, m);
      if (res.data.ok) setData(res.data);
    } catch {
      Alert.alert("Error", "Failed to load attendance.");
    }
    setLoading(false);
  };

  useEffect(() => { load(year, month); }, [year, month]);

  const handleMonthChange = (y, m) => {
    setYear(y); setMonth(m);
  };

  return (
    <LinearGradient colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]} style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#173B8C" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Attendance History</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <MonthPicker year={year} month={month} onChange={handleMonthChange} />

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator size="large" color="#173B8C" />
          </View>
        ) : !data ? null : (
          <>
            {/* Summary cards */}
            <View style={styles.summaryRow}>
              {[
                { label: "Present",   value: data.summary.present,   color: "#22C55E", bg: "#DCFCE7" },
                { label: "Full Days", value: data.summary.full_days,  color: "#3B82F6", bg: "#EFF6FF" },
                { label: "Half Days", value: data.summary.half_days,  color: "#F59E0B", bg: "#FFFBEB" },
                { label: "Late",      value: data.summary.late,       color: "#EF4444", bg: "#FEF2F2" },
              ].map(s => (
                <View key={s.label} style={[styles.summaryCard, { backgroundColor: s.bg }]}>
                  <Text style={[styles.summaryNum, { color: s.color }]}>{s.value}</Text>
                  <Text style={[styles.summaryLabel, { color: s.color }]}>{s.label}</Text>
                </View>
              ))}
            </View>

            {/* Records list */}
            {data.records.length === 0 ? (
              <View style={styles.empty}>
                <Ionicons name="calendar-outline" size={48} color="#CBD5E1" />
                <Text style={styles.emptyTxt}>No records for this month</Text>
              </View>
            ) : data.records.map((r, i) => {
              const typeStyle = TYPE_COLOR[r.attendance_type] || { bg: "#F1F5F9", text: "#64748B" };
              const d = new Date(r.date);
              const dayName = d.toLocaleDateString("en-US", { weekday: "short" });
              const dayNum  = d.getDate();
              return (
                <View key={i} style={styles.row}>
                  {/* Date badge */}
                  <View style={styles.dateBadge}>
                    <Text style={styles.dayNum}>{dayNum}</Text>
                    <Text style={styles.dayName}>{dayName}</Text>
                  </View>
                  {/* Details */}
                  <View style={styles.details}>
                    <View style={styles.timesRow}>
                      <View style={styles.timeBox}>
                        <Ionicons name="log-in-outline" size={14} color="#22C55E" />
                        <Text style={styles.timeVal}>{r.login_time || "--:--"}</Text>
                      </View>
                      <Ionicons name="arrow-forward" size={12} color="#CBD5E1" style={{ marginHorizontal: 6 }} />
                      <View style={styles.timeBox}>
                        <Ionicons name="log-out-outline" size={14} color="#EF4444" />
                        <Text style={styles.timeVal}>{r.logout_time || "--:--"}</Text>
                      </View>
                      <View style={styles.hoursBox}>
                        <Ionicons name="time-outline" size={13} color="#64748B" />
                        <Text style={styles.hoursVal}>{fmtMinutes(r.worked_minutes)}</Text>
                      </View>
                    </View>
                    <View style={styles.statusRow}>
                      <Text style={[styles.typeBadge, { backgroundColor: typeStyle.bg, color: typeStyle.text }]}>
                        {r.attendance_type || "No Record"}
                      </Text>
                      {r.login_status && (
                        <Text style={[styles.loginStatus, { color: STATUS_COLOR[r.login_status] || "#64748B" }]}>
                          {r.login_status}
                        </Text>
                      )}
                    </View>
                  </View>
                </View>
              );
            })}
          </>
        )}
        <View style={{ height: 40 }} />
      </ScrollView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    paddingTop: 55, paddingHorizontal: 20, paddingBottom: 16,
    backgroundColor: "#FFFFFF",
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  backBtn:     { width: 40, height: 40, borderRadius: 12, backgroundColor: "#EEF4FF", justifyContent: "center", alignItems: "center" },
  headerTitle: { fontSize: 16, fontWeight: "700", color: "#0F172A" },
  scroll:      { padding: 20 },
  center:      { alignItems: "center", paddingVertical: 60 },
  summaryRow:  { flexDirection: "row", justifyContent: "space-between", marginBottom: 20 },
  summaryCard: { flex: 1, marginHorizontal: 3, borderRadius: 14, padding: 12, alignItems: "center" },
  summaryNum:  { fontSize: 18, fontWeight: "800" },
  summaryLabel:{ fontSize: 11, fontWeight: "600", marginTop: 2 },
  empty:       { alignItems: "center", paddingVertical: 50 },
  emptyTxt:    { color: "#94A3B8", fontSize: 13, marginTop: 12 },
  row: {
    flexDirection: "row", backgroundColor: "#FFFFFF", borderRadius: 16, marginBottom: 10,
    padding: 14, alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  dateBadge:  { width: 48, alignItems: "center", marginRight: 14 },
  dayNum:     { fontSize: 18, fontWeight: "800", color: "#0F172A" },
  dayName:    { fontSize: 11, color: "#94A3B8", fontWeight: "600" },
  details:    { flex: 1 },
  timesRow:   { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  timeBox:    { flexDirection: "row", alignItems: "center" },
  timeVal:    { fontSize: 13, fontWeight: "700", color: "#0F172A", marginLeft: 4 },
  hoursBox:   { flexDirection: "row", alignItems: "center", marginLeft: "auto" },
  hoursVal:   { fontSize: 12, color: "#64748B", marginLeft: 3 },
  statusRow:  { flexDirection: "row", alignItems: "center", gap: 8 },
  typeBadge:  { fontSize: 11, fontWeight: "700", paddingHorizontal: 10, paddingVertical: 4, borderRadius: 20 },
  loginStatus:{ fontSize: 11, fontWeight: "600" },
});
