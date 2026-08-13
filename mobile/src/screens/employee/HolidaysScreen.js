import React, { useState, useEffect } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  ActivityIndicator,
  RefreshControl,
  StyleSheet,
} from "react-native";

import ProfileHeader from "../../components/profile/ProfileHeader";
import HolidayHeaderCard from "../../components/holidays/HolidayHeaderCard";
import HolidaySummaryCard from "../../components/holidays/HolidaySummaryCard";
import YearSelector from "../../components/holidays/YearSelector";
import HolidayLegend from "../../components/holidays/HolidayLegend";
import HolidayCalendar from "../../components/holidays/HolidayCalendar";
import HolidayList from "../../components/holidays/HolidayList";
import EmptyHolidayCard from "../../components/holidays/EmptyHolidayCard";
import { fetchEmployeeHolidays } from "../../api/client";

export default function HolidaysScreen() {
  const [year, setYear] = useState(2026);
  const [selectedDate, setSelectedDate] = useState(null);
  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadHolidays = async () => {
    try {
      const res = await fetchEmployeeHolidays();
      if (res?.data?.holidays && Array.isArray(res.data.holidays)) {
        setHolidays(res.data.holidays);
      } else if (Array.isArray(res?.data)) {
        setHolidays(res.data);
      } else {
        setHolidays([]);
      }
    } catch (_) {
      setHolidays([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadHolidays();
  }, []);
  return (
    <SafeAreaView style={styles.container}>
      <ProfileHeader
        title="Holiday Calendar"
        showBack={false}
      />

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
      >
        {/* Header */}

        <HolidayHeaderCard
          year={year}
          totalHolidays={18}
          publicHolidays={12}
          optionalHolidays={4}
          companyHolidays={2}
        />

        {/* Upcoming */}

        <HolidaySummaryCard
          upcomingHoliday="Independence Day"
          holidayDate="15 August 2026"
          remainingDays={46}
          holidayType="Public Holiday"
        />

        {/* Year */}

        <YearSelector
          year={year}
          onPrevious={() =>
            setYear(year - 1)
          }
          onNext={() =>
            setYear(year + 1)
          }
        />

        {/* Legend */}

        <HolidayLegend />

        {/* Calendar */}

        <HolidayCalendar
          month={5}
          year={year}
          holidays={holidays}
          selectedDate={selectedDate}
          onDatePress={(day) =>
            setSelectedDate(day)
          }
        />

        {/* Holiday List */}

        <Text style={styles.sectionTitle}>
          Holidays
        </Text>

        {holidays.length > 0 ? (
          <HolidayList
            holidays={holidays}
          />
        ) : (
          <EmptyHolidayCard />
        )}

        <View
          style={{
            height: 40,
          }}
        />
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
    marginTop: 26,
    marginBottom: 16,

    fontSize: 22,

    fontWeight: "800",

    color: "#0F172A",

    letterSpacing: -0.5,
  },

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 20,

    marginBottom: 18,

    borderWidth: 1,

    borderColor: "#E8EDF3",

    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 3,
  },

  row: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    paddingVertical: 12,

    borderBottomWidth: 1,

    borderBottomColor: "#EEF2F7",
  },

  rowLeft: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  rowRight: {
    alignItems: "flex-end",
  },

  iconContainer: {
    width: 42,
    height: 42,

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
    marginTop: 3,

    fontSize: 13,

    color: "#64748B",
  },

  value: {
    fontSize: 16,

    fontWeight: "800",

    color: "#173B8C",
  },

  badge: {
    marginTop: 6,

    paddingHorizontal: 12,

    paddingVertical: 5,

    borderRadius: 16,

    backgroundColor: "#EEF4FF",
  },

  badgeText: {
    color: "#173B8C",

    fontWeight: "700",

    fontSize: 12,
  },

  infoCard: {
    marginTop: 20,

    backgroundColor: "#EEF4FF",

    borderLeftWidth: 4,

    borderLeftColor: "#173B8C",

    borderRadius: 18,

    padding: 18,
  },

  infoTitle: {
    fontSize: 16,

    fontWeight: "800",

    color: "#173B8C",

    marginBottom: 8,
  },

  infoText: {
    color: "#475569",

    fontSize: 14,

    lineHeight: 22,

    fontWeight: "500",
  },

  divider: {
    height: 1,

    backgroundColor: "#EEF2F7",

    marginVertical: 20,
  },

  footerCard: {
    marginTop: 20,

    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 20,

    borderWidth: 1,

    borderColor: "#E8EDF3",

    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 3,
  },

  footerTitle: {
    fontSize: 18,

    fontWeight: "800",

    color: "#0F172A",

    marginBottom: 10,
  },

  footerText: {
    fontSize: 14,

    lineHeight: 22,

    color: "#64748B",
  },

  statsRow: {
    flexDirection: "row",

    justifyContent: "space-between",

    marginTop: 18,
  },

  statBox: {
    flex: 1,

    backgroundColor: "#FFFFFF",

    borderRadius: 18,

    paddingVertical: 16,

    alignItems: "center",

    marginHorizontal: 4,

    borderWidth: 1,

    borderColor: "#E8EDF3",

    shadowColor: "#0F172A",
    shadowOpacity: 0.03,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 3,
    },

    elevation: 2,
  },

  statNumber: {
    marginTop: 6,

    fontSize: 24,

    fontWeight: "800",

    color: "#173B8C",
  },

  statLabel: {
    marginTop: 4,

    fontSize: 12,

    color: "#64748B",

    fontWeight: "600",

    textAlign: "center",
  },
});