import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

export default function IncentiveCard({

  employee,

  amount,

  reason,

  onPress,

}) {

  return (

    <TouchableOpacity
      activeOpacity={0.9}
      style={styles.card}
      onPress={onPress}
    >

      {/* Accent */}

      <View style={styles.accent} />

      {/* Header */}

      <View style={styles.header}>

        <View style={styles.leftSection}>

          <View style={styles.iconContainer}>

            <Ionicons
              name="wallet-outline"
              size={24}
              color={PERFORMANCE_THEME.colors.success}
            />

          </View>

          <View style={styles.info}>

            <Text
              numberOfLines={1}
              style={styles.name}
            >
              {employee}
            </Text>

            <Text style={styles.reason}>
              {reason}
            </Text>

          </View>

        </View>

        <View style={styles.badge}>

          <Text style={styles.badgeText}>
            Bonus
          </Text>

        </View>

      </View>

      {/* Amount */}

      <View style={styles.amountSection}>

        <Text style={styles.amountLabel}>
          Incentive Amount
        </Text>

        <Text style={styles.amount}>
          ₹{amount}
        </Text>

      </View>

      {/* Footer */}

      <View style={styles.footer}>

        <View style={styles.footerLeft}>

          <Ionicons
            name="checkmark-circle"
            size={16}
            color={PERFORMANCE_THEME.colors.success}
          />

          <Text style={styles.footerText}>
            Approved by HR
          </Text>

        </View>

        <Ionicons
          name="chevron-forward"
          size={18}
          color="#94A3B8"
        />

      </View>

    </TouchableOpacity>

  );

}

const styles = StyleSheet.create({

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    padding: 20,

    marginBottom: 18,

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

    backgroundColor:
      PERFORMANCE_THEME.colors.success,
  },

  header: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",
  },

  leftSection: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  iconContainer: {
    width: 56,

    height: 56,

    borderRadius: 18,

    backgroundColor: "#ECFDF5",

    justifyContent: "center",

    alignItems: "center",

    marginRight: 14,
  },

  info: {
    flex: 1,
  },

  name: {
    fontSize: 17,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.textPrimary,
  },

  reason: {
    marginTop: 4,

    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  badge: {
    backgroundColor: "#ECFDF5",

    paddingHorizontal: 12,

    paddingVertical: 6,

    borderRadius: 16,
  },

  badgeText: {
    fontSize: 11,

    fontWeight: "800",

    color:
      PERFORMANCE_THEME.colors.success,
  },

  amountSection: {
    marginTop: 24,
  },

  amountLabel: {
    fontSize: 13,

    fontWeight: "600",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

  amount: {
    marginTop: 6,

    fontSize: 34,

    fontWeight: "900",

    color:
      PERFORMANCE_THEME.colors.success,
  },

  footer: {
    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    marginTop: 22,

    paddingTop: 18,

    borderTopWidth: 1,

    borderTopColor: "#EEF2F7",
  },

  footerLeft: {
    flexDirection: "row",

    alignItems: "center",
  },

  footerText: {
    marginLeft: 6,

    fontSize: 12,

    fontWeight: "700",

    color:
      PERFORMANCE_THEME.colors.textMuted,
  },

});
