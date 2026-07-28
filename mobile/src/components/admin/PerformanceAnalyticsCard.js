import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceAnalyticsCard({

  completionRate,

  averageKPI,

  highestRating,

  topPerformer,

  onPress,

}) {

  return (

    <TouchableOpacity
      activeOpacity={0.9}
      style={styles.card}
      onPress={onPress}
    >

      {/* Decorative Circles */}

      <View style={styles.circleOne} />

      <View style={styles.circleTwo} />

      {/* ================= HEADER ================= */}

      <View style={styles.header}>

        <View style={styles.leftSection}>

          <View style={styles.iconContainer}>

            <Ionicons
              name="analytics"
              size={26}
              color="#FFFFFF"
            />

          </View>

          <View>

            <Text style={styles.title}>
              Performance Analytics
            </Text>

            <Text style={styles.subtitle}>
              Quarterly Insights
            </Text>

          </View>

        </View>

        <View style={styles.liveChip}>

          <View style={styles.liveDot} />

          <Text style={styles.liveText}>
            LIVE
          </Text>

        </View>

      </View>

      {/* ================= HERO ================= */}

      <View style={styles.heroSection}>

        <View>

          <Text style={styles.heroValue}>
            {completionRate}%

            <Text style={styles.heroUnit}>
              {" "}Done
            </Text>

          </Text>

          <Text style={styles.heroLabel}>
            Review Completion
          </Text>

          <View style={styles.trendRow}>

            <Ionicons
              name="trending-up"
              size={16}
              color="#22C55E"
            />

            <Text style={styles.trendText}>
              +6.8% from previous quarter
            </Text>

          </View>

        </View>

        <View style={styles.scoreCard}>

          <Ionicons
            name="star"
            size={26}
            color="#F59E0B"
          />

          <Text style={styles.scoreValue}>
            {highestRating}
          </Text>

          <Text style={styles.scoreLabel}>
            Highest Rating
          </Text>

        </View>

      </View>
            {/* ================= KPI GRID ================= */}

      <View style={styles.kpiGrid}>

        <View style={styles.kpiCard}>

          <View
            style={[
              styles.kpiIcon,
              {
                backgroundColor: "#DBEAFE",
              },
            ]}
          >

            <Ionicons
              name="analytics-outline"
              size={20}
              color="#2563EB"
            />

          </View>

          <Text style={styles.kpiValue}>
            {averageKPI}%
          </Text>

          <Text style={styles.kpiLabel}>
            Average KPI
          </Text>

        </View>

        <View style={styles.kpiCard}>

          <View
            style={[
              styles.kpiIcon,
              {
                backgroundColor: "#ECFDF5",
              },
            ]}
          >

            <Ionicons
              name="person-outline"
              size={20}
              color="#10B981"
            />

          </View>

          <Text
            numberOfLines={1}
            style={styles.topPerformer}
          >
            {topPerformer}
          </Text>

          <Text style={styles.kpiLabel}>
            Top Performer
          </Text>

        </View>

      </View>

      {/* ================= PROGRESS ================= */}

      <View style={styles.progressSection}>

        <View style={styles.progressHeader}>

          <Text style={styles.progressTitle}>
            Overall Review Progress
          </Text>

          <Text style={styles.progressPercent}>
            {completionRate}%
          </Text>

        </View>

        <View style={styles.progressTrack}>

          <View
            style={[
              styles.progressFill,
              {
                width: `${completionRate}%`,
              },
            ]}
          />

        </View>

      </View>

      {/* ================= TOP PERFORMER ================= */}

      <View style={styles.performerCard}>

        <View style={styles.performerAvatar}>

          <Ionicons
            name="trophy"
            size={24}
            color="#F59E0B"
          />

        </View>

        <View style={styles.performerContent}>

          <Text style={styles.performerTitle}>
            Employee of the Quarter
          </Text>

          <Text style={styles.performerName}>
            {topPerformer}
          </Text>

          <Text style={styles.performerDescription}>
            Outstanding leadership and KPI achievement
          </Text>

        </View>

        <View style={styles.ratingChip}>

          <Ionicons
            name="star"
            size={14}
            color="#F59E0B"
          />

          <Text style={styles.ratingText}>
            {highestRating}
          </Text>

        </View>

      </View>

      {/* ================= FOOTER ================= */}

      <View style={styles.footer}>

        <View style={styles.footerItem}>

          <Ionicons
            name="flash-outline"
            size={16}
            color="rgba(255,255,255,0.85)"
          />

          <Text style={styles.footerText}>
            AI Insights
          </Text>

        </View>

        <View style={styles.footerDivider} />

        <View style={styles.footerItem}>

          <Ionicons
            name="shield-checkmark-outline"
            size={16}
            color="rgba(255,255,255,0.85)"
          />

          <Text style={styles.footerText}>
            Updated Today
          </Text>

        </View>

      </View>

    </TouchableOpacity>

  );

}
const styles = StyleSheet.create({

  card: {
    backgroundColor: PERFORMANCE_THEME.colors.primary,

    borderRadius: 30,

    paddingHorizontal: 24,

    paddingTop: 24,

    paddingBottom: 24,

    marginBottom: 24,

    overflow: "hidden",

    shadowColor: PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.25,

    shadowRadius: 22,

    shadowOffset: {
      width: 0,
      height: 10,
    },

    elevation: 12,
  },

  circleOne: {
    position: "absolute",

    top: -70,

    right: -60,

    width: 190,

    height: 190,

    borderRadius: 95,

    backgroundColor: "rgba(255,255,255,0.06)",
  },

  circleTwo: {
    position: "absolute",

    bottom: -90,

    left: -60,

    width: 170,

    height: 170,

    borderRadius: 85,

    backgroundColor: "rgba(255,255,255,0.05)",
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  leftSection: {
    flexDirection: "row",

    alignItems: "center",
  },

  iconContainer: {
    width: 58,

    height: 58,

    borderRadius: 18,

    backgroundColor: "rgba(255,255,255,0.15)",

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  title: {
    fontSize: 22,

    fontWeight: "900",

    color: "#FFFFFF",
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    fontWeight: "600",

    color: "rgba(255,255,255,0.72)",
  },

  liveChip: {
    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "rgba(255,255,255,0.16)",

    paddingHorizontal: 12,

    paddingVertical: 7,

    borderRadius: 20,
  },

  liveDot: {
    width: 8,

    height: 8,

    borderRadius: 4,

    backgroundColor: "#22C55E",

    marginRight: 6,
  },

  liveText: {
    color: "#FFFFFF",

    fontSize: 11,

    fontWeight: "800",

    letterSpacing: 0.5,
  },

  heroSection: {
    marginTop: 28,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  heroValue: {
    fontSize: 48,

    fontWeight: "900",

    color: "#FFFFFF",

    letterSpacing: -2,
  },

  heroUnit: {
    fontSize: 22,

    fontWeight: "700",

    color: "rgba(255,255,255,0.82)",
  },

  heroLabel: {
    marginTop: 6,

    fontSize: 14,

    fontWeight: "600",

    color: "rgba(255,255,255,0.82)",
  },

  trendRow: {
    flexDirection: "row",

    alignItems: "center",

    marginTop: 14,
  },

  trendText: {
    marginLeft: 6,

    fontSize: 12,

    fontWeight: "700",

    color: "#DCFCE7",
  },

  scoreCard: {
    width: 130,

    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    paddingVertical: 18,

    alignItems: "center",

    shadowColor: "#000",

    shadowOpacity: 0.08,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 6,
    },

    elevation: 6,
  },

  scoreValue: {
    marginTop: 10,

    fontSize: 30,

    fontWeight: "900",

    color: PERFORMANCE_THEME.colors.textPrimary,
  },

  scoreLabel: {
    marginTop: 4,

    fontSize: 12,

    fontWeight: "700",

    color: PERFORMANCE_THEME.colors.textMuted,

    textAlign: "center",
  },

  kpiGrid: {
    flexDirection: "row",

    justifyContent: "space-between",

    marginTop: 30,
  },

  kpiCard: {
    flex: 1,

    backgroundColor: "rgba(255,255,255,0.10)",

    borderRadius: 20,

    paddingVertical: 18,

    paddingHorizontal: 16,

    marginHorizontal: 4,
  },

  kpiIcon: {
    width: 46,

    height: 46,

    borderRadius: 15,

    justifyContent: "center",

    alignItems: "center",

    marginBottom: 14,
  },

  kpiValue: {
    fontSize: 26,

    fontWeight: "900",

    color: "#FFFFFF",
  },

  topPerformer: {
    fontSize: 18,

    fontWeight: "800",

    color: "#FFFFFF",
  },

  kpiLabel: {
    marginTop: 5,

    fontSize: 12,

    fontWeight: "600",

    color: "rgba(255,255,255,0.75)",
  },

  progressSection: {
    marginTop: 28,
  },

  progressHeader: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginBottom: 10,
  },

  progressTitle: {
    fontSize: 14,

    fontWeight: "700",

    color: "#FFFFFF",
  },

  progressPercent: {
    fontSize: 14,

    fontWeight: "800",

    color: "#FFFFFF",
  },

  progressTrack: {
    height: 10,

    borderRadius: 30,

    backgroundColor: "rgba(255,255,255,0.18)",

    overflow: "hidden",
  },

  progressFill: {
    height: "100%",

    borderRadius: 30,

    backgroundColor: "#22C55E",
  },
    performerCard: {
    marginTop: 28,

    backgroundColor: "rgba(255,255,255,0.10)",

    borderRadius: 22,

    paddingHorizontal: 18,

    paddingVertical: 18,

    flexDirection: "row",

    alignItems: "center",
  },

  performerAvatar: {
    width: 58,

    height: 58,

    borderRadius: 18,

    backgroundColor: "#FFFFFF",

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  performerContent: {
    flex: 1,
  },

  performerTitle: {
    fontSize: 12,

    fontWeight: "700",

    color: "rgba(255,255,255,0.70)",

    textTransform: "uppercase",

    letterSpacing: 0.5,
  },

  performerName: {
    marginTop: 4,

    fontSize: 18,

    fontWeight: "900",

    color: "#FFFFFF",
  },

  performerDescription: {
    marginTop: 5,

    fontSize: 13,

    lineHeight: 18,

    color: "rgba(255,255,255,0.78)",
  },

  ratingChip: {
    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#FFFFFF",

    paddingHorizontal: 12,

    paddingVertical: 8,

    borderRadius: 18,
  },

  ratingText: {
    marginLeft: 5,

    fontSize: 14,

    fontWeight: "900",

    color: PERFORMANCE_THEME.colors.textPrimary,
  },

  footer: {
    marginTop: 26,

    paddingTop: 18,

    borderTopWidth: 1,

    borderTopColor: "rgba(255,255,255,0.14)",

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  footerItem: {
    flex: 1,

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",
  },

  footerDivider: {
    width: 1,

    height: 24,

    backgroundColor: "rgba(255,255,255,0.18)",
  },

  footerText: {
    marginLeft: 8,

    fontSize: 12,

    fontWeight: "700",

    color: "rgba(255,255,255,0.82)",
  },

});