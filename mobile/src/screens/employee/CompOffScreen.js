import React from "react";
import {
  ScrollView,
  StyleSheet,
  RefreshControl,
  View,
  TouchableOpacity,
  Text,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";

import CompOffHeaderCard from "../../components/compoff/CompOffHeaderCard";
import CompOffStatsGrid from "../../components/compoff/CompOffStatsGrid";
import CompOffInfoCard from "../../components/compoff/CompOffInfoCard";
import OvertimeHistoryCard from "../../components/compoff/OvertimeHistoryCard";
import CompOffApplicationCard from "../../components/compoff/CompOffApplicationCard";
import ProfileHeader from "../../components/profile/ProfileHeader";

export default function CompOffScreen() {
  const navigation = useNavigation();
const today = new Date();
  const overtimeRecords = [
    {
      date: "12 Jun 2026",
      day: "Friday",
      hours: "3h 20m",
      compOff: "0.5 Day",
      approvedBy: "Manager",
      status: "Approved",
    },
    {
      date: "20 Jun 2026",
      day: "Saturday",
      hours: "8h 00m",
      compOff: "1 Day",
      approvedBy: "HR",
      status: "Approved",
    },
    {
      date: "25 Jun 2026",
      day: "Thursday",
      hours: "2h 30m",
      compOff: "0 Day",
      approvedBy: "Pending",
      status: "Pending",
    },
  ];

  const applications = [
    {
      date: "18 Jun 2026",
      reason: "Weekend Production Support",
      days: "1 Day",
      approvedBy: "HR",
      status: "Approved",
    },
    {
      date: "26 Jun 2026",
      reason: "Release Deployment",
      days: "0.5 Day",
      approvedBy: "--",
      status: "Pending",
    },
  ];

  return (
  <LinearGradient
    colors={[
      "#F8FAFC",
      "#F6F9FE",
      "#EEF4FF",
    ]}
    style={styles.container}
  >

    <ProfileHeader title="Comp-Off Requests" subtitle="EMPLOYEE PORTAL" />

    <ScrollView
      showsVerticalScrollIndicator={false}
      contentContainerStyle={styles.content}
    >

      {/* Your existing components */}

      <CompOffHeaderCard />

      <CompOffStatsGrid />

      <CompOffInfoCard />

      <OvertimeHistoryCard
        records={overtimeRecords}
      />

      <CompOffApplicationCard
        applications={applications}
      />

    </ScrollView>

  </LinearGradient>
);
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  content: {
  paddingHorizontal: 18,
  paddingTop: 0,
  paddingBottom: 120,
},
  header: {
  paddingHorizontal: 20,
  paddingTop: 56,
  paddingBottom: 18,
  flexDirection: "row",
  alignItems: "center",
  justifyContent: "space-between",
},

headerCenter: {
  flex: 1,
  alignItems: "center",
},

iconButton: {
  width: 46,
  height: 46,
  borderRadius: 14,
  backgroundColor: "#FFFFFF",
  justifyContent: "center",
  alignItems: "center",

  shadowColor: "#000",
  shadowOpacity: 0.05,
  shadowRadius: 8,
  shadowOffset: {
    width: 0,
    height: 3,
  },

  elevation: 4,
},

smallTitle: {
  fontSize: 13,
  color: "#64748B",
  fontWeight: "600",
},

title: {
  marginTop: 3,
  fontSize: 18,
  color: "#0F172A",
  fontWeight: "800",
},

date: {
  marginTop: 4,
  fontSize: 13,
  color: "#94A3B8",
},
});