import React, { useState, useEffect } from "react";
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, Alert, RefreshControl,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { fetchEmployeeSalary } from "../../api/client";

const MONTHS = ["January","February","March","April","May","June",
                 "July","August","September","October","November","December"];

function MonthPicker({ year, month, onChange }) {
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
  label: { width: 180, textAlign: "center", fontSize: 17, fontWeight: "700", color: "#0F172A" },
});

function Row({ label, value, bold, highlight }) {
  return (
    <View style={[row.wrap, highlight && row.highlighted]}>
      <Text style={[row.label, bold && row.bold]}>{label}</Text>
      <Text style={[row.value, bold && row.bold, highlight && row.highlightVal]}>{value}</Text>
    </View>
  );
}

const row = StyleSheet.create({
  wrap:        { flexDirection: "row", justifyContent: "space-between", paddingVertical: 12, borderBottomWidth: 1, borderColor: "#F1F5F9" },
  highlighted: { backgroundColor: "#EEF4FF", borderRadius: 10, paddingHorizontal: 10, borderBottomWidth: 0, marginHorizontal: -10 },
  label:       { fontSize: 14, color: "#64748B" },
  bold:        { fontWeight: "700", color: "#0F172A" },
  value:       { fontSize: 14, color: "#0F172A" },
  highlightVal:{ color: "#173B8C", fontSize: 16 },
});

export default function PayslipsScreen({ navigation }) {
  const now = new Date();
  const [year, setYear]     = useState(now.getFullYear());
  const [month, setMonth]   = useState(now.getMonth() + 1);
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async (y, m) => {
    setLoading(true);
    try {
      const res = await fetchEmployeeSalary(y, m);
      if (res.data.ok) setData(res.data);
      else Alert.alert("Error", res.data.msg || "Failed to load salary.");
    } catch {
      Alert.alert("Error", "Failed to connect to server.");
    }
    setLoading(false);
  };

  useEffect(() => { load(year, month); }, [year, month]);

  const fmt = (val) => `₹ ${Number(val).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

  const s = data?.salary;

  return (
    <LinearGradient colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]} style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#173B8C" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Payslips</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={() => load(year, month)} />
        }
      >
        <MonthPicker year={year} month={month} onChange={(y, m) => { setYear(y); setMonth(m); }} />

        {loading ? (
          <View style={styles.center}><ActivityIndicator size="large" color="#173B8C" /></View>
        ) : !s ? (
          <View style={{ backgroundColor: "#FFFFFF", borderRadius: 20, padding: 30, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#E2E8F0", marginTop: 20 }}>
            <Ionicons name="document-text-outline" size={48} color="#94A3B8" />
            <Text style={{ fontSize: 16, fontWeight: "700", color: "#0F172A", marginTop: 12 }}>No Payslip Generated Yet</Text>
            <Text style={{ fontSize: 13, color: "#64748B", textAlign: "center", marginTop: 6 }}>
              Payslips for {MONTHS[month - 1]} {year} have not been published by payroll administration yet.
            </Text>
          </View>
        ) : (
          <>
            {/* Net Pay Hero */}
            <LinearGradient colors={["#0B2253", "#173B8C"]} style={styles.hero} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}>
              <Text style={styles.heroLabel}>Net Pay — {data.month_name}</Text>
              <Text style={styles.heroAmount}>{fmt(s.net)}</Text>
              <Text style={styles.heroSub}>{s.name} · {s.emp_id}</Text>
            </LinearGradient>

            {/* Attendance breakdown */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Attendance Breakdown</Text>
              <Row label="Billable Working Days" value={`${s.billable} days`} />
              <Row label="Full Days Present"      value={`${s.full_days} days`} />
              <Row label="Half Days Present"      value={`${s.half_days} days`} />
              <Row label="Late Days"              value={`${s.late_days} days`} />
              <Row label="Approved Leave Days"    value={`${s.leave_days} days`} />
              <Row label="Absent Days"            value={`${s.absent} days`} />
            </View>

            {/* Earnings */}
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Salary Calculation</Text>
              <Row label="Daily Rate"   value={fmt(s.spd)} />
              <Row label="Gross Pay"    value={fmt(s.gross)} />
              <Row label="Deductions"   value={`- ${fmt(s.deduction)}`} />
              <Row label="Net Pay" value={fmt(s.net)} bold highlight />
            </View>
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
  hero: {
    borderRadius: 20, padding: 24, marginBottom: 16, alignItems: "center",
  },
  heroLabel:  { color: "rgba(255,255,255,0.8)", fontSize: 12, fontWeight: "600" },
  heroAmount: { color: "#FFFFFF", fontSize: 24, fontWeight: "800", marginTop: 4 },
  heroSub:    { color: "rgba(255,255,255,0.7)", fontSize: 12, marginTop: 4 },
  card: {
    backgroundColor: "#FFFFFF", borderRadius: 18, padding: 18, marginBottom: 14,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  cardTitle: { fontSize: 13, fontWeight: "700", color: "#0F172A", marginBottom: 8 },
});
