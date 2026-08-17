import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function PerformanceHeaderCard({
  quarter,
  month,
  year,
  averageRating,
  totalEmployees,
  onSettings,
}) {
  const progress = Math.min(
    (averageRating / 5) * 100,
    100
  );

  return (
    <View style={styles.card}>

      {/* Decorative Background */}

      <View style={styles.circleOne} />

      <View style={styles.circleTwo} />

      {/* ================= HEADER ================= */}

      <View style={styles.header}>

        <View style={styles.leftSection}>

          <View style={styles.iconContainer}>

            <Ionicons
              name="bar-chart-outline"
              size={28}
              color="#FFFFFF"
            />

          </View>

          <View>

            <Text style={styles.title}>
              Performance
            </Text>

            <Text style={styles.subtitle}>
              Employee Reviews & Ratings
            </Text>

          </View>

        </View>

        <TouchableOpacity
          activeOpacity={0.85}
          style={styles.settingsButton}
          onPress={onSettings}
        >

          <Ionicons
            name="options-outline"
            size={22}
            color="#FFFFFF"
          />

        </TouchableOpacity>

      </View>

      {/* Quarter */}

      <View style={styles.quarterChip}>

        <Ionicons
          name="calendar-outline"
          size={15}
          color="#FFFFFF"
        />

        <Text style={styles.quarterText}>
          {quarter} • {month} {year}
        </Text>

      </View>

      {/* ================= HERO ================= */}

      <View style={styles.heroSection}>

        <View style={{ flex: 1 }}>

          <Text style={styles.heroLabel}>
            Average Rating
          </Text>

          <Text style={styles.heroValue}>
            {Number(
              averageRating || 0
            ).toFixed(1)}

            <Text style={styles.heroUnit}>
              /5
            </Text>

          </Text>

          <View style={styles.trendRow}>

            <View style={styles.trendChip}>

              <Ionicons
                name="trending-up"
                size={14}
                color="#16A34A"
              />

              <Text style={styles.trendText}>
                +8%
              </Text>

            </View>

            <Text style={styles.compareText}>
              compared to last quarter
            </Text>

          </View>

        </View>
                  {/* Floating KPI Card */}

          <View style={styles.ratingCard}>

            <View style={styles.ratingIcon}>

              <Ionicons
                name="star"
                size={24}
                color="#F59E0B"
              />

            </View>

            <Text style={styles.ratingValue}>
              {Number(
                averageRating || 0
              ).toFixed(1)}
            </Text>

            <Text style={styles.ratingLabel}>
              Overall Score
            </Text>

            <View style={styles.ratingBadge}>

              <Ionicons
                name="checkmark-circle"
                size={13}
                color="#10B981"
              />

              <Text style={styles.ratingBadgeText}>
                Excellent
              </Text>

            </View>

          </View>

        </View>

      {/* ================= KPI CARDS ================= */}

      <View style={styles.statsRow}>

        <View style={styles.statCard}>

          <View
            style={[
              styles.statIcon,
              {
                backgroundColor:
                  "rgba(255,255,255,0.16)",
              },
            ]}
          >

            <Ionicons
              name="people-outline"
              size={20}
              color="#FFFFFF"
            />

          </View>

          <View style={styles.statContent}>

            <Text style={styles.statValue}>
              {totalEmployees}
            </Text>

            <Text style={styles.statTitle}>
              Employees
            </Text>

          </View>

        </View>

        <View style={styles.statCard}>

          <View
            style={[
              styles.statIcon,
              {
                backgroundColor:
                  "rgba(255,255,255,0.16)",
              },
            ]}
          >

            <Ionicons
              name="trophy-outline"
              size={20}
              color="#FFFFFF"
            />

          </View>

          <View style={styles.statContent}>

            <Text style={styles.statValue}>
              {Number(
                averageRating || 0
              ).toFixed(1)}
            </Text>

            <Text style={styles.statTitle}>
              Avg Rating
            </Text>

          </View>

        </View>

      </View>

      {/* ================= PROGRESS ================= */}

      <View style={styles.progressContainer}>

        <View style={styles.progressHeader}>

          <Text style={styles.progressTitle}>
            Review Completion
          </Text>

          <Text style={styles.progressPercent}>
            {Math.round(progress)}%
          </Text>

        </View>

        <View style={styles.progressTrack}>

          <View
            style={[
              styles.progressFill,
              {
                width: `${progress}%`,
              },
            ]}
          />

        </View>

      </View>

      {/* ================= FOOTER ================= */}

      <View style={styles.footer}>

        <View style={styles.footerItem}>

          <Ionicons
            name="document-text-outline"
            size={16}
            color="rgba(255,255,255,0.85)"
          />

          <Text style={styles.footerText}>
            Quarterly Reviews
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
            HR Verified
          </Text>

        </View>

      </View>

    </View>

  );

}
const styles = StyleSheet.create({

  card: {
    backgroundColor: "#1D4ED8",

    borderRadius: 30,

    paddingHorizontal: 24,

    paddingTop: 24,

    paddingBottom: 24,

    marginBottom: 24,

    overflow: "hidden",

    shadowColor: "#1D4ED8",

    shadowOpacity: 0.28,

    shadowRadius: 22,

    shadowOffset: {
      width: 0,
      height: 12,
    },

    elevation: 16,
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

    zIndex: 2,
  },

  leftSection: {
    flexDirection: "row",

    alignItems: "center",
  },

  iconContainer: {
    width: 58,

    height: 58,

    borderRadius: 18,

    backgroundColor: "rgba(255,255,255,0.16)",

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  title: {
    fontSize: 24,

    fontWeight: "900",

    color: "#FFFFFF",

    letterSpacing: -0.6,
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    color: "rgba(255,255,255,0.75)",
  },

  settingsButton: {
    width: 48,

    height: 48,

    borderRadius: 16,

    backgroundColor: "rgba(255,255,255,0.14)",

    justifyContent: "center",

    alignItems: "center",
  },

  quarterChip: {
    alignSelf: "flex-start",

    marginTop: 22,

    paddingHorizontal: 14,

    paddingVertical: 8,

    borderRadius: 50,

    backgroundColor: "rgba(255,255,255,0.12)",

    flexDirection: "row",

    alignItems: "center",
  },

  quarterText: {
    marginLeft: 6,

    color: "#FFFFFF",

    fontWeight: "700",

    fontSize: 13,
  },

  heroSection: {
    marginTop: 28,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  heroLabel: {
    fontSize: 15,

    color: "rgba(255,255,255,0.80)",

    fontWeight: "600",
  },

  heroValue: {
    marginTop: 6,

    fontSize: 50,

    fontWeight: "900",

    color: "#FFFFFF",

    letterSpacing: -2,
  },

  heroUnit: {
    fontSize: 26,

    fontWeight: "700",

    color: "rgba(255,255,255,0.82)",
  },

  trendRow: {
    flexDirection: "row",

    alignItems: "center",

    marginTop: 14,
  },

  trendChip: {
    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#FFFFFF",

    paddingHorizontal: 10,

    paddingVertical: 5,

    borderRadius: 30,
  },

  trendText: {
    marginLeft: 4,

    fontSize: 12,

    fontWeight: "800",

    color: "#16A34A",
  },

  compareText: {
    marginLeft: 10,

    color: "rgba(255,255,255,0.78)",

    fontSize: 12,

    fontWeight: "600",
  },

  ratingCard: {
    width: 140,

    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    paddingVertical: 18,

    paddingHorizontal: 14,

    alignItems: "center",

    shadowColor: "#000",

    shadowOpacity: 0.08,

    shadowRadius: 14,

    shadowOffset: {
      width: 0,
      height: 8,
    },

    elevation: 8,
  },

  ratingIcon: {
    width: 54,

    height: 54,

    borderRadius: 16,

    backgroundColor: "#FEF3C7",

    justifyContent: "center",

    alignItems: "center",
  },

  ratingValue: {
    marginTop: 14,

    fontSize: 32,

    fontWeight: "900",

    color: PERFORMANCE_THEME.colors.textPrimary,
  },

  ratingLabel: {
    marginTop: 4,

    fontSize: 12,

    fontWeight: "700",

    color: PERFORMANCE_THEME.colors.textMuted,

    textAlign: "center",
  },

  ratingBadge: {
    marginTop: 14,

    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#ECFDF5",

    paddingHorizontal: 10,

    paddingVertical: 5,

    borderRadius: 20,
  },

  ratingBadgeText: {
    marginLeft: 5,

    fontSize: 11,

    fontWeight: "800",

    color: "#16A34A",
  },
    statsRow: {
    flexDirection: "row",

    justifyContent: "space-between",

    marginTop: 28,
  },

  statCard: {
    flex: 1,

    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "rgba(255,255,255,0.10)",

    borderRadius: 18,

    paddingVertical: 16,

    paddingHorizontal: 16,

    marginHorizontal: 4,
  },

  statIcon: {
    width: 42,

    height: 42,

    borderRadius: 14,

    justifyContent: "center",

    alignItems: "center",

    marginRight: 12,
  },

  statContent: {
    flex: 1,
  },

  statValue: {
    fontSize: 22,

    fontWeight: "900",

    color: "#FFFFFF",

    letterSpacing: -0.5,
  },

  statTitle: {
    marginTop: 3,

    fontSize: 12,

    fontWeight: "600",

    color: "rgba(255,255,255,0.72)",
  },

  progressContainer: {
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

  footer: {
    marginTop: 24,

    paddingTop: 18,

    borderTopWidth: 1,

    borderTopColor: "rgba(255,255,255,0.12)",

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  footerItem: {
    flex: 1,

    flexDirection: "row",

    alignItems: "center",

    justifyContent: "center",
  },

  footerDivider: {
    width: 1,

    height: 22,

    backgroundColor: "rgba(255,255,255,0.20)",
  },

  footerText: {
    marginLeft: 8,

    fontSize: 12,

    fontWeight: "700",

    color: "rgba(255,255,255,0.82)",
  },

});