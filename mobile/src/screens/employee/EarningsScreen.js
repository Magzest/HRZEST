import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  SafeAreaView,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";
import ProfileHeader from "../../components/profile/ProfileHeader";

import HeaderCard from "../../components/earnings/HeaderCard";
import SummaryCard from "../../components/earnings/SummaryCard";
import BreakdownRow from "../../components/earnings/BreakdownRow";
import PayslipCard from "../../components/earnings/PayslipCard";
import StatChip from "../../components/earnings/StatChip";

import { StyleSheet } from "react-native";
import { fetchEmployeeSalary } from "../../api/client";

export default function EarningsScreen() {
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [earnings, setEarnings] = useState(null);
  const [error, setError] = useState("");

  const loadSalary = async () => {
    setError("");
    try {
      const res = await fetchEmployeeSalary(year, month);
      if (res?.data?.ok) {
        // API returns data nested under res.data.salary
        setEarnings(res.data.salary ?? res.data);
      } else {
        setError(res?.data?.msg || "Could not load salary data.");
      }
    } catch {
      setError("Unable to connect to server. Please try again.");
    }
    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => { loadSalary(); }, [month, year]);

  const monthName = new Date(year, month - 1).toLocaleString("en-IN", { month: "long" });

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { justifyContent: "center", alignItems: "center" }]}>
        <ActivityIndicator size="large" color="#173B8C" />
        <Text style={{ marginTop: 12, color: "#64748B", fontWeight: "600" }}>Loading salary data…</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader title="Earnings" showBack={false} />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => { setRefreshing(true); loadSalary(); }}
            colors={["#173B8C"]}
          />
        }
      >
        {error ? (
          <View style={{ backgroundColor: "#FEF2F2", borderRadius: 12, padding: 16, marginBottom: 20, borderWidth: 1, borderColor: "#FECACA" }}>
            <Text style={{ color: "#DC2626", fontWeight: "600", textAlign: "center" }}>{error}</Text>
          </View>
        ) : null}

        {earnings ? (
          <>
            <HeaderCard
              month={monthName}
              year={String(year)}
              total={earnings.net ?? earnings.gross ?? 0}
              grossPay={earnings.gross ?? 0}
              incentives={earnings.incentives ?? 0}
              overtime={earnings.overtime ?? 0}
            />

            <View style={styles.chipContainer}>
              <StatChip label="Salary Credited" color="#16A34A" background="#DCFCE7" />
              <StatChip label="Payslip Available" color="#173B8C" background="#EEF4FF" />
            </View>

            <Text style={styles.sectionTitle}>Salary Summary</Text>

            <SummaryCard icon="wallet-outline" title="Gross Pay" value={earnings.gross ?? 0} color="#173B8C" background="#EEF4FF" />
            <SummaryCard icon="trophy-outline" title="Deductions" value={earnings.deduction ?? 0} color="#EF4444" background="#FEF2F2" />
            <SummaryCard icon="cash-outline" title="Net Pay" value={earnings.net ?? 0} color="#16A34A" background="#DCFCE7" />

            <Text style={styles.sectionTitle}>Monthly Breakdown</Text>

            <View style={styles.breakdownCard}>
              <BreakdownRow icon="checkmark-circle-outline" label="Full Days" value={`${earnings.full_days ?? "--"} Days`} color="#16A34A" background="#DCFCE7" valueColor="#16A34A" />
              <BreakdownRow icon="remove-circle-outline" label="Half Days" value={`${earnings.half_days ?? "--"} Days`} color="#F59E0B" background="#FFF7ED" valueColor="#D97706" />
              <BreakdownRow icon="alarm-outline" label="Late Days" value={`${earnings.late_days ?? "--"} Days`} color="#EA580C" background="#FFF7ED" valueColor="#EA580C" />
              <BreakdownRow icon="close-circle-outline" label="Absent" value={`${earnings.absent ?? "--"} Days`} color="#EF4444" background="#FEF2F2" valueColor="#DC2626" />
              <BreakdownRow icon="calendar-outline" label="Approved Leaves" value={`${earnings.leave_days ?? "--"} Days`} color="#8B5CF6" background="#EDE9FE" valueColor="#7C3AED" />
              <BreakdownRow icon="cash-outline" label="Daily Rate" value={earnings.spd ? `₹${Number(earnings.spd).toLocaleString()}` : "--"} color="#173B8C" background="#EEF4FF" valueColor="#173B8C" />
            </View>

            <PayslipCard onViewPayslip={() => navigation.navigate("Payslips")} />
          </>
        ) : (
          <View style={{ backgroundColor: "#FFFFFF", borderRadius: 20, padding: 30, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: "#E2E8F0", marginTop: 20 }}>
            <Ionicons name="wallet-outline" size={48} color="#94A3B8" />
            <Text style={{ fontSize: 16, fontWeight: "700", color: "#0F172A", marginTop: 12 }}>No Salary Record Published</Text>
            <Text style={{ fontSize: 13, color: "#64748B", textAlign: "center", marginTop: 6 }}>
              Earnings details for {monthName} {year} will be displayed here once generated by payroll admin.
            </Text>
          </View>
        )}

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

  chipContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginBottom: 22,
  },

  sectionTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 12,
    marginTop: 6,
  },

  breakdownCard: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    paddingHorizontal: 18,
    paddingVertical: 8,

    borderWidth: 1,
    borderColor: "#E8EDF3",

    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 2,

    marginBottom: 22,
  },

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 20,

    padding: 18,

    borderWidth: 1,
    borderColor: "#E8EDF3",

    marginBottom: 18,

    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 2,
  },

  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 14,
  },

  cardTitle: {
    marginLeft: 10,
    fontSize: 14,
    fontWeight: "800",
    color: "#0F172A",
  },

  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",

    paddingVertical: 10,

    borderBottomWidth: 1,
    borderBottomColor: "#EEF2F7",
  },

  rowLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#475569",
  },

  rowValue: {
    fontSize: 16,
    fontWeight: "800",
    color: "#173B8C",
  },

  infoCard: {
    backgroundColor: "#EEF4FF",

    borderRadius: 18,

    padding: 16,

    marginTop: 20,
    marginBottom: 18,

    borderLeftWidth: 4,
    borderLeftColor: "#173B8C",
  },

  infoTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: "#173B8C",
    marginBottom: 8,
  },

  infoText: {
    fontSize: 14,
    lineHeight: 22,
    color: "#475569",
    fontWeight: "500",
  },

  divider: {
    height: 1,
    backgroundColor: "#EEF2F7",
    marginVertical: 18,
  },

  footerCard: {
    backgroundColor: "#FFFFFF",

    borderRadius: 20,

    padding: 18,

    borderWidth: 1,
    borderColor: "#E8EDF3",

    marginTop: 20,

    shadowColor: "#0F172A",
    shadowOpacity: 0.04,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 2,
  },

  footerTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: "#0F172A",
    marginBottom: 10,
  },

  footerText: {
    fontSize: 14,
    lineHeight: 22,
    color: "#64748B",
  },
});