import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

import PerformanceStatusChip from "./PerformanceStatusChip";

export default function EmployeeReviewCard({

  employee,

  onPress,

  onReview,

}) {

  const initials =
    employee.avatar ||
    employee.name
      ?.split(" ")
      .map((item) => item[0])
      .join("")
      .substring(0, 2)
      .toUpperCase();

  return (

    <TouchableOpacity
      activeOpacity={0.92}
      style={styles.card}
      onPress={onPress}
    >

      {/* Top Accent */}

      <View
        style={[
          styles.accent,
          {
            backgroundColor:
              employee.completed
                ? PERFORMANCE_THEME.colors.success
                : PERFORMANCE_THEME.colors.warning,
          },
        ]}
      />

      {/* ================= HEADER ================= */}

      <View style={styles.header}>

        <View style={styles.leftSection}>

          {/* Avatar */}

          <View style={styles.avatar}>

            <Text style={styles.avatarText}>
              {initials}
            </Text>

          </View>

          <View style={styles.info}>

            <Text
              numberOfLines={1}
              style={styles.name}
            >
              {employee.name}
            </Text>

            <Text style={styles.designation}>
              {employee.designation}
            </Text>

            <View style={styles.departmentRow}>

              <Ionicons
                name="business-outline"
                size={13}
                color={
                  PERFORMANCE_THEME.colors.textMuted
                }
              />

              <Text style={styles.department}>
                {employee.department}
              </Text>

            </View>

          </View>

        </View>

        <PerformanceStatusChip
          status={employee.status}
        />

      </View>

      {/* ================= RATING ================= */}

      <View style={styles.ratingSection}>

        <View style={styles.ratingLeft}>

          <Ionicons
            name="star"
            size={18}
            color="#F59E0B"
          />

          <Text style={styles.ratingValue}>
            {employee.rating || "—"}
          </Text>

          <Text style={styles.ratingLabel}>
            Overall Rating
          </Text>

        </View>

        <View style={styles.kpiCard}>

          <Text style={styles.kpiValue}>
            {employee.kpis}
          </Text>

          <Text style={styles.kpiLabel}>
            KPIs
          </Text>

        </View>

      </View>
            {/* ================= PROGRESS ================= */}

      <View style={styles.progressContainer}>

        <View style={styles.progressHeader}>

          <Text style={styles.progressTitle}>
            Review Progress
          </Text>

          <Text style={styles.progressPercent}>
            {employee.progress}%
          </Text>

        </View>

        <View style={styles.progressTrack}>

          <View
            style={[
              styles.progressFill,
              {
                width: `${employee.progress}%`,
                backgroundColor:
                  employee.completed
                    ? PERFORMANCE_THEME.colors.success
                    : PERFORMANCE_THEME.colors.warning,
              },
            ]}
          />

        </View>

      </View>

      {/* ================= STRENGTHS ================= */}

      {employee.strengths &&
      employee.strengths.length > 0 ? (

        <View style={styles.strengthSection}>

          <Text style={styles.sectionTitle}>
            Key Strengths
          </Text>

          <View style={styles.tagContainer}>

            {employee.strengths.map(
              (item, index) => (

                <View
                  key={index}
                  style={styles.tag}
                >

                  <Text style={styles.tagText}>
                    {item}
                  </Text>

                </View>

              )
            )}

          </View>

        </View>

      ) : null}

      {/* ================= INCENTIVE ================= */}

      <View style={styles.bottomRow}>

        <View style={styles.incentiveCard}>

          <Ionicons
            name="cash-outline"
            size={18}
            color={
              PERFORMANCE_THEME.colors.success
            }
          />

          <View
            style={styles.incentiveContent}
          >

            <Text
              style={styles.incentiveLabel}
            >
              Incentive
            </Text>

            <Text
              style={styles.incentiveValue}
            >
              ₹{employee.incentive}
            </Text>

          </View>

        </View>

        <TouchableOpacity
          activeOpacity={0.9}
          style={styles.reviewButton}
          onPress={onReview}
        >

          <Text
            style={styles.reviewButtonText}
          >
            {employee.completed
              ? "View Review"
              : "Start Review"}
          </Text>

          <Ionicons
            name="arrow-forward"
            size={18}
            color="#FFFFFF"
          />

        </TouchableOpacity>

      </View>

    </TouchableOpacity>

  );

}
const styles = StyleSheet.create({

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 28,

    marginBottom: 20,

    paddingHorizontal: 20,

    paddingTop: 20,

    paddingBottom: 20,

    overflow: "hidden",

    borderWidth: 1,

    borderColor: "#EEF2F7",

    shadowColor: "#0F172A",

    shadowOpacity: 0.06,

    shadowRadius: 18,

    shadowOffset: {
      width: 0,
      height: 8,
    },

    elevation: 6,
  },

  accent: {
    position: "absolute",

    top: 0,

    left: 0,

    right: 0,

    height: 5,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "flex-start",
  },

  leftSection: {
    flexDirection: "row",

    flex: 1,

    marginRight: 10,
  },

  avatar: {
    width: 64,

    height: 64,

    borderRadius: 20,

    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    justifyContent: "center",

    alignItems: "center",

    marginRight: 16,
  },

  avatarText: {
    fontSize: 22,

    fontWeight: "900",

    color: "#FFFFFF",
  },

  info: {
    flex: 1,

    justifyContent: "center",
  },

  name: {
    fontSize: 18,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  designation: {
    marginTop: 4,

    fontSize: 14,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

  departmentRow: {
    flexDirection: "row",

    alignItems: "center",

    marginTop: 8,
  },

  department: {
    marginLeft: 5,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  ratingSection: {
    marginTop: 24,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  ratingLeft: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  ratingValue: {
    marginLeft: 8,

    fontSize: 26,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  ratingLabel: {
    marginLeft: 8,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  kpiCard: {
    width: 84,

    height: 84,

    borderRadius: 22,

    backgroundColor:
      PERFORMANCE_THEME.colors.primaryLight,

    justifyContent: "center",

    alignItems: "center",
  },

  kpiValue: {
    fontSize: 26,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.primary,
  },

  kpiLabel: {
    marginTop: 4,

    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  progressContainer: {
    marginTop: 24,
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

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  progressPercent: {
    fontSize: 14,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.primary,
  },

  progressTrack: {
    height: 10,

    borderRadius: 20,

    backgroundColor: "#E5E7EB",

    overflow: "hidden",
  },

  progressFill: {
    height: "100%",

    borderRadius: 20,
  },
    strengthSection: {
    marginTop: 24,
  },

  sectionTitle: {
    fontSize: 14,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,

    marginBottom: 12,
  },

  tagContainer: {
    flexDirection: "row",

    flexWrap: "wrap",
  },

  tag: {
    backgroundColor: "#F8FAFC",

    borderWidth: 1,

    borderColor:
      PERFORMANCE_THEME.colors.border,

    paddingHorizontal: 12,

    paddingVertical: 8,

    borderRadius: 16,

    marginRight: 8,

    marginBottom: 8,
  },

  tagText: {
    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textSecondary,
  },

  bottomRow: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginTop: 26,
  },

  incentiveCard: {
    flex: 1,

    flexDirection: "row",

    alignItems: "center",

    backgroundColor: "#F8FAFC",

    borderRadius: 18,

    borderWidth: 1,

    borderColor:
      PERFORMANCE_THEME.colors.border,

    paddingHorizontal: 14,

    paddingVertical: 14,

    marginRight: 12,
  },

  incentiveContent: {
    marginLeft: 10,
  },

  incentiveLabel: {
    fontSize: 11,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  incentiveValue: {
    marginTop: 3,

    fontSize: 17,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.success,
  },

  reviewButton: {
    height: 54,

    paddingHorizontal: 20,

    borderRadius: 18,

    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.22,

    shadowRadius: 12,

    shadowOffset: {
      width: 0,
      height: 5,
    },

    elevation: 6,
  },

  reviewButtonText: {
    color: "#FFFFFF",

    fontSize: 14,

    fontWeight: "800",

    marginRight: 8,
  },

});