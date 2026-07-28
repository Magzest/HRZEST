import React from "react";

import {
  View,
  Text,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import COMPOFF_THEME from "../../constants/compOffTheme";

export default function CompOffBalanceCard({
  availableDays,
  usedDays,
  remainingDays,
  expiryDate,
}) {
  const total =
    availableDays + usedDays;

  const percentage =
    total > 0
      ? (remainingDays / total) * 100
      : 0;

  return (
    <View style={styles.card}>

      {/* Header */}

      <View style={styles.header}>

        <View>

          <Text style={styles.title}>
            Comp-off Balance
          </Text>

          <Text style={styles.subtitle}>
            Available Leave Credits
          </Text>

        </View>

        <View style={styles.iconBox}>
          <Ionicons
            name="calendar-clear"
            size={24}
            color={COMPOFF_THEME.colors.success}
          />
        </View>

      </View>

      {/* Balance */}

      <View style={styles.balanceContainer}>

        <Text style={styles.balanceValue}>
          {remainingDays}
        </Text>

        <Text style={styles.balanceLabel}>
          Days Available
        </Text>

      </View>

      {/* Progress */}

      <View style={styles.progressSection}>

        <View style={styles.progressBackground}>

          <View
            style={[
              styles.progressFill,
              {
                width: `${percentage}%`,
              },
            ]}
          />

        </View>

        <View style={styles.progressRow}>

          <Text style={styles.progressText}>
            {percentage.toFixed(0)}% Remaining
          </Text>

          <Text style={styles.progressText}>
            {availableDays} Days Earned
          </Text>

        </View>

      </View>

      {/* Statistics */}

      <View style={styles.statsContainer}>

        <View style={styles.statCard}>

          <Text style={styles.statValue}>
            {availableDays}
          </Text>

          <Text style={styles.statLabel}>
            Earned
          </Text>

        </View>

        <View style={styles.divider} />

        <View style={styles.statCard}>

          <Text
            style={[
              styles.statValue,
              {
                color:
                  COMPOFF_THEME.colors.warning,
              },
            ]}
          >
            {usedDays}
          </Text>

          <Text style={styles.statLabel}>
            Used
          </Text>

        </View>

        <View style={styles.divider} />

        <View style={styles.statCard}>

          <Text
            style={[
              styles.statValue,
              {
                color:
                  COMPOFF_THEME.colors.success,
              },
            ]}
          >
            {remainingDays}
          </Text>

          <Text style={styles.statLabel}>
            Remaining
          </Text>

        </View>

      </View>

      {/* Footer */}

      <View style={styles.footer}>

        <Ionicons
          name="alarm-outline"
          size={18}
          color={COMPOFF_THEME.colors.textMuted}
        />

        <Text style={styles.footerText}>
          Expires on {expiryDate}
        </Text>

      </View>

    </View>
  );
}

const styles = StyleSheet.create({

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    padding: 20,

    marginBottom: 20,

    borderWidth: 1,

    borderColor:
      COMPOFF_THEME.colors.border,

    ...COMPOFF_THEME.shadow,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  title: {
    fontSize: 20,

    fontWeight: "800",

    color:
      COMPOFF_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    color:
      COMPOFF_THEME.colors.textMuted,
  },

  iconBox: {
    width: 56,

    height: 56,

    borderRadius: 18,

    backgroundColor:
      COMPOFF_THEME.colors.successLight,

    justifyContent: "center",

    alignItems: "center",
  },

  balanceContainer: {
    alignItems: "center",

    marginTop: 28,
  },

  balanceValue: {
    fontSize: 54,

    fontWeight: "900",

    color:
      COMPOFF_THEME.colors.success,
  },

  balanceLabel: {
    marginTop: 6,

    fontSize: 15,

    fontWeight: "600",

    color:
      COMPOFF_THEME.colors.textMuted,
  },

  progressSection: {
    marginTop: 26,
  },

  progressBackground: {
    height: 10,

    borderRadius: 12,

    backgroundColor:
      COMPOFF_THEME.colors.divider,

    overflow: "hidden",
  },

  progressFill: {
    height: "100%",

    backgroundColor:
      COMPOFF_THEME.colors.success,

    borderRadius: 12,
  },

  progressRow: {
    marginTop: 10,

    flexDirection: "row",

    justifyContent: "space-between",
  },

  progressText: {
    fontSize: 12,

    fontWeight: "700",

    color:
      COMPOFF_THEME.colors.textMuted,
  },

  statsContainer: {
    flexDirection: "row",

    alignItems: "center",

    marginTop: 24,
  },

  statCard: {
    flex: 1,

    alignItems: "center",
  },

  divider: {
    width: 1,

    height: 42,

    backgroundColor:
      COMPOFF_THEME.colors.divider,
  },

  statValue: {
    fontSize: 24,

    fontWeight: "900",

    color:
      COMPOFF_THEME.colors.textPrimary,
  },

  statLabel: {
    marginTop: 4,

    fontSize: 12,

    fontWeight: "700",

    color:
      COMPOFF_THEME.colors.textMuted,
  },

  footer: {
    flexDirection: "row",

    alignItems: "center",

    marginTop: 22,

    paddingTop: 18,

    borderTopWidth: 1,

    borderTopColor:
      COMPOFF_THEME.colors.divider,
  },

  footerText: {
    marginLeft: 8,

    fontSize: 13,

    fontWeight: "600",

    color:
      COMPOFF_THEME.colors.textMuted,
  },

});