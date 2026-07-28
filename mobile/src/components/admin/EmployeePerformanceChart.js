import React from "react";

import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function EmployeePerformanceChart({

  monthlyData = [],

  averageScore = 4.6,

  improvement = "+12%",

}) {

  const maxValue = Math.max(
    ...monthlyData.map(item => item.score),
    5
  );

  return (

    <View style={styles.container}>

      {/* ================= HEADER ================= */}

      <View style={styles.header}>

        <View>

          <Text style={styles.title}>
            Performance Trend
          </Text>

          <Text style={styles.subtitle}>
            Monthly employee rating overview
          </Text>

        </View>

        <View style={styles.liveBadge}>

          <View style={styles.liveDot} />

          <Text style={styles.liveText}>
            Live
          </Text>

        </View>

      </View>

      {/* ================= SUMMARY ================= */}

      <View style={styles.summaryCard}>

        <View style={styles.summaryItem}>

          <Ionicons
            name="star"
            size={20}
            color="#F59E0B"
          />

          <Text style={styles.summaryValue}>
            {averageScore}
          </Text>

          <Text style={styles.summaryLabel}>
            Average Rating
          </Text>

        </View>

        <View style={styles.divider} />

        <View style={styles.summaryItem}>

          <Ionicons
            name="trending-up"
            size={20}
            color="#10B981"
          />

          <Text style={styles.summaryValue}>
            {improvement}
          </Text>

          <Text style={styles.summaryLabel}>
            Growth
          </Text>

        </View>

      </View>

      {/* ================= CHART ================= */}

      <View style={styles.chartContainer}>

        <View style={styles.chartArea}></View>

                  {monthlyData.map((item, index) => {

            const barHeight =
              (item.score / maxValue) * 160;

            const isHighest =
              item.score ===
              Math.max(
                ...monthlyData.map(
                  data => data.score
                )
              );

            return (

              <View
                key={index}
                style={styles.barColumn}
              >

                <Text
                  style={[
                    styles.valueLabel,
                    isHighest &&
                      styles.bestValueLabel,
                  ]}
                >
                  {item.score}
                </Text>

                <View
                  style={styles.barWrapper}
                >

                  <View
                    style={[
                      styles.bar,

                      {
                        height: Math.max(
                          barHeight,
                          12
                        ),
                      },

                      isHighest &&
                        styles.bestBar,
                    ]}
                  />

                </View>

                <Text
                  style={[
                    styles.monthLabel,

                    isHighest &&
                      styles.bestMonthLabel,
                  ]}
                >
                  {item.month}
                </Text>

              </View>

            );

          })}

        </View>

      </View>

      {/* ================= LEGEND ================= */}

      <View style={styles.legendContainer}>

        <View style={styles.legendItem}>

          <View
            style={styles.normalLegend}
          />

          <Text style={styles.legendText}>
            Performance
          </Text>

        </View>

        <View style={styles.legendItem}>

          <View
            style={styles.bestLegend}
          />

          <Text style={styles.legendText}>
            Best Month
          </Text>

        </View>

      </View>

    </View>

  );

}
const styles = StyleSheet.create({

  container: {
    backgroundColor: "#FFFFFF",

    borderRadius: 28,

    padding: 22,

    marginBottom: 20,

    borderWidth: 1,

    borderColor: "#EEF2F7",

    shadowColor: "#0F172A",

    shadowOpacity: 0.05,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 4,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 20,
  },

  title: {
    fontSize: 22,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  liveBadge: {
    flexDirection: "row",

    alignItems: "center",

    paddingHorizontal: 12,

    paddingVertical: 7,

    borderRadius: 999,

    backgroundColor: "#ECFDF5",

    borderWidth: 1,

    borderColor: "#A7F3D0",
  },

  liveDot: {
    width: 8,

    height: 8,

    borderRadius: 4,

    backgroundColor: "#10B981",

    marginRight: 7,
  },

  liveText: {
    fontSize: 12,

    fontWeight: "800",

    color: "#047857",
  },

  summaryCard: {
    flexDirection: "row",

    alignItems: "center",

    justifyContent: "space-between",

    backgroundColor: "#F8FAFC",

    borderRadius: 22,

    paddingVertical: 18,

    paddingHorizontal: 20,

    marginBottom: 26,

    borderWidth: 1,

    borderColor: "#E2E8F0",
  },

  summaryItem: {
    flex: 1,

    alignItems: "center",
  },

  divider: {
    width: 1,

    height: 54,

    backgroundColor: "#E2E8F0",
  },

  summaryValue: {
    marginTop: 8,

    fontSize: 24,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  summaryLabel: {
    marginTop: 4,

    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  chartContainer: {
    backgroundColor: "#FCFDFE",

    borderRadius: 22,

    paddingHorizontal: 16,

    paddingVertical: 22,

    borderWidth: 1,

    borderColor: "#EEF2F7",
  },

  chartArea: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "flex-end",

    height: 210,
  },

  barColumn: {
    flex: 1,

    alignItems: "center",
  },

  valueLabel: {
    marginBottom: 8,

    fontSize: 12,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

  bestValueLabel: {
    color:
      PERFORMANCE_THEME.colors.primary,
  },

  barWrapper: {
    width: 26,

    height: 160,

    justifyContent: "flex-end",

    alignItems: "center",
  },

  bar: {
    width: 24,

    borderRadius: 14,

    backgroundColor: "#CBD5E1",
  },

  bestBar: {
    backgroundColor:
      PERFORMANCE_THEME.colors.primary,
  },

  monthLabel: {
    marginTop: 12,

    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  bestMonthLabel: {
    color:
      PERFORMANCE_THEME.colors.primary,
  },
    legendContainer: {
    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",

    marginTop: 22,

    paddingTop: 18,

    borderTopWidth: 1,

    borderTopColor: "#EEF2F7",
  },

  legendItem: {
    flexDirection: "row",

    alignItems: "center",

    marginHorizontal: 14,
  },

  normalLegend: {
    width: 14,

    height: 14,

    borderRadius: 4,

    backgroundColor: "#CBD5E1",

    marginRight: 8,
  },

  bestLegend: {
    width: 14,

    height: 14,

    borderRadius: 4,

    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    marginRight: 8,
  },

  legendText: {
    fontSize: 13,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

});