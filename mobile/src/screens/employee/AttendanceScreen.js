import React, { useEffect, useState } from "react";
import {
  View,
  ScrollView,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
  Text,
} from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";

import { fetchEmployeeAttendance } from "../../api/client";

import LoadingSkeleton from "../../components/ui/LoadingSkeleton";

import MonthYearPicker from "../../components/attendance/MonthYearPicker";
import AttendanceSummaryCard from "../../components/attendance/AttendanceSummaryCard";
import AttendanceStatusCard from "../../components/attendance/AttendanceStatusCard";
import AttendanceCalendar from "../../components/attendance/AttendanceCalendar";
import AttendanceLegend from "../../components/attendance/AttendanceLegend";
import AttendanceHistoryCard from "../../components/attendance/AttendanceHistoryCard";
import AttendanceEmptyState from "../../components/attendance/AttendanceEmptyState";

import ProfileHeader from "../../components/profile/ProfileHeader";

export default function AttendanceScreen() {
  const navigation = useNavigation();

  const today = new Date();

  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [attendance, setAttendance] = useState([]);

  const loadAttendance = async () => {
    try {
      const res = await fetchEmployeeAttendance(year, month);

      if (res.data?.ok) {
        setAttendance(res.data.records || []);
      } else {
        setAttendance([]);
      }
    } catch {
      setAttendance([]);
    }

    setLoading(false);
    setRefreshing(false);
  };

  useEffect(() => {
    loadAttendance();
  }, [month, year]);

  const previousMonth = () => {
    if (month === 1) {
      setMonth(12);
      setYear((y) => y - 1);
    } else {
      setMonth((m) => m - 1);
    }
  };

  const nextMonth = () => {
    if (month === 12) {
      setMonth(1);
      setYear((y) => y + 1);
    } else {
      setMonth((m) => m + 1);
    }
  };

  const present = attendance.filter(
    (x) => x.status === "Present"
  ).length;

  const absent = attendance.filter(
    (x) => x.status === "Absent"
  ).length;

  const late = attendance.filter(
    (x) => x.status === "Late"
  ).length;

  const percentage =
    attendance.length === 0
      ? 0
      : Math.round(
          (present / attendance.length) * 100
        );

  const latest =
    attendance.length > 0
      ? attendance[attendance.length - 1]
      : {};

  if (loading) {
    return (
      <LinearGradient
        colors={["#F8FAFC", "#F2F7FD", "#EDF4FF"]}
        style={{ flex: 1 }}
      >
        <LoadingSkeleton />
      </LinearGradient>
    );
  }

  return (
    <LinearGradient
      colors={["#F8FAFC", "#F3F7FD", "#EDF4FF"]}
      style={styles.container}
    >
      <ProfileHeader title="Attendance Logs" subtitle="EMPLOYEE PORTAL" />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadAttendance();
            }}
            colors={["#173B8C"]}
          />
        }
      >
        <MonthYearPicker
          month={month}
          year={year}
          onPrevious={previousMonth}
          onNext={nextMonth}
        />

        <AttendanceSummaryCard
          percentage={percentage}
          present={present}
          absent={absent}
          late={late}
        />

        <AttendanceStatusCard
          checkIn={latest.check_in || "--:--"}
          checkOut={latest.check_out || "--:--"}
          workingHours={latest.hours || "--"}
          status={latest.status || "Not Marked"}
        />

        {attendance.length > 0 ? (
          <>
            <AttendanceCalendar
              month={month}
              year={year}
              records={attendance}
            />

            <AttendanceLegend />

            <AttendanceHistoryCard
              records={attendance}
            />
          </>
        ) : (
          <AttendanceEmptyState />
        )}
      </ScrollView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },

  header: {
    paddingHorizontal: 20,
    paddingTop: 56,
    paddingBottom: 18,

    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  menuButton: {
    width: 46,
    height: 46,
    borderRadius: 14,

    backgroundColor: "#FFFFFF",

    justifyContent: "center",
    alignItems: "center",

    elevation: 4,

    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 3,
    },
  },

  profile: {
    width: 46,
    height: 46,
    borderRadius: 14,

    backgroundColor: "#FFFFFF",

    justifyContent: "center",
    alignItems: "center",

    elevation: 4,

    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 3,
    },
  },

  smallTitle: {
    fontSize: 13,
    color: "#64748B",
    textAlign: "center",
    fontWeight: "600",
  },

  title: {
    marginTop: 3,
    fontSize: 28,
    color: "#0F172A",
    fontWeight: "800",
    textAlign: "center",
  },

  content: {
    paddingHorizontal: 18,
    paddingBottom: 120,
  },
});