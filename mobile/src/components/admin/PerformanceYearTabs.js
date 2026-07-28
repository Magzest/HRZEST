import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

const YEARS = [
  "2024",
  "2025",
  "2026",
  "2027",
];

export default function PerformanceYearTabs({
  selectedYear,
  onChange,
}) {
  return (
    <View style={styles.container}>

      {/* Header */}

      <View style={styles.header}>

        <Text style={styles.title}>
          Review Year
        </Text>

        <Text style={styles.subtitle}>
          Select Financial Year
        </Text>

      </View>

      {/* Tabs */}

      <View style={styles.wrapper}>

        {YEARS.map((year) => {

          const active =
            String(selectedYear) === year;

          return (

            <TouchableOpacity
              key={year}
              activeOpacity={0.9}
              onPress={() =>
                onChange(year)
              }
              style={[
                styles.tab,
                active &&
                  styles.activeTab,
              ]}
            >

              <Text
                style={[
                  styles.tabText,
                  active &&
                    styles.activeTabText,
                ]}
              >
                {year}
              </Text>

            </TouchableOpacity>

          );

        })}

      </View>

    </View>
  );
}

const styles = StyleSheet.create({

  container: {
    marginBottom: 24,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 14,
  },

  title: {
    fontSize: 17,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  wrapper: {
    flexDirection: "row",

    justifyContent: "space-between",

    backgroundColor: "#EEF2F7",

    padding: 6,

    borderRadius: 24,

    borderWidth: 1,

    borderColor:
      PERFORMANCE_THEME.colors.border,
  },

  tab: {
    flex: 1,

    height: 52,

    borderRadius: 18,

    justifyContent: "center",

    alignItems: "center",
  },

  activeTab: {
    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.18,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 4,
    },

    elevation: 5,
  },

  tabText: {
    fontSize: 14,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

  activeTabText: {
    color: "#FFFFFF",

    fontWeight: "800",
  },

});