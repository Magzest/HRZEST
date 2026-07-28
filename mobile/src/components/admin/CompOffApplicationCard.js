import React from "react";

import {
  View,
  Text,
 TouchableOpacity,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import COMPOFF_THEME from "../../constants/compOffTheme";
import CompOffStatusChip from "./CompOffStatusChip";

export default function CompOffApplicationCard({
  item,
  onPress,
}) {
  return (
    <TouchableOpacity
      activeOpacity={0.9}
      style={styles.card}
      onPress={() => onPress?.(item)}
    >
      {/* Header */}

      <View style={styles.header}>

        <View style={styles.profileSection}>

          <View style={styles.avatar}>

            <Ionicons
              name="person"
              size={22}
              color={COMPOFF_THEME.colors.primary}
            />

          </View>

          <View style={styles.profileInfo}>

            <Text style={styles.name}>
              {item.employeeName}
            </Text>

            <Text style={styles.department}>
              {item.department}
            </Text>

          </View>

        </View>

        <CompOffStatusChip
          status={item.status}
        />

      </View>

      {/* Leave Period */}

      <View style={styles.periodCard}>

        <View style={styles.periodItem}>

          <Ionicons
            name="calendar-outline"
            size={18}
            color={COMPOFF_THEME.colors.primary}
          />

          <Text style={styles.periodText}>
            {item.startDate}
          </Text>

        </View>

        <Ionicons
          name="arrow-forward"
          size={18}
          color={COMPOFF_THEME.colors.textMuted}
        />

        <View style={styles.periodItem}>

          <Ionicons
            name="calendar-outline"
            size={18}
            color={COMPOFF_THEME.colors.success}
          />

          <Text style={styles.periodText}>
            {item.endDate}
          </Text>

        </View>

      </View>

      {/* Reason */}

      <View style={styles.reasonCard}>

        <Text style={styles.reasonTitle}>
          Reason
        </Text>

        <Text style={styles.reason}>
          {item.reason}
        </Text>

      </View>

      {/* Footer */}

      <View style={styles.footer}>

        <View style={styles.footerItem}>

          <Ionicons
            name="time-outline"
            size={18}
            color={COMPOFF_THEME.colors.warning}
          />

          <Text style={styles.footerValue}>
            {item.days} Day(s)
          </Text>

        </View>

        <View style={styles.footerDivider} />

        <View style={styles.footerItem}>

          <Ionicons
            name="briefcase-outline"
            size={18}
            color={COMPOFF_THEME.colors.primary}
          />

          <Text style={styles.footerValue}>
            Comp-off
          </Text>

        </View>

      </View>

    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({

  card: {
    backgroundColor: "#FFFFFF",

    borderRadius: 24,

    padding: 18,

    marginBottom: 18,

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

  profileSection: {
    flexDirection: "row",

    alignItems: "center",

    flex: 1,
  },

  avatar: {
    width: 54,

    height: 54,

    borderRadius: 18,

    backgroundColor:
      COMPOFF_THEME.colors.primaryLight,

    justifyContent: "center",

    alignItems: "center",
  },

  profileInfo: {
    marginLeft: 14,
    flex: 1,
  },

  name: {
    fontSize: 17,

    fontWeight: "800",

    color:
      COMPOFF_THEME.colors.textPrimary,
  },

  department: {
    marginTop: 4,

    fontSize: 13,

    color:
      COMPOFF_THEME.colors.textMuted,
  },

  periodCard: {
    marginTop: 18,

    flexDirection: "row",

    justifyContent: "space-between",

    alignItems: "center",

    backgroundColor: "#F8FAFC",

    borderRadius: 18,

    padding: 16,
  },

  periodItem: {
    flexDirection: "row",

    alignItems: "center",
  },

  periodText: {
    marginLeft: 8,

    fontSize: 14,

    fontWeight: "700",

    color:
      COMPOFF_THEME.colors.textPrimary,
  },

  reasonCard: {
    marginTop: 16,

    backgroundColor: "#F8FAFC",

    borderRadius: 18,

    padding: 16,
  },

  reasonTitle: {
    fontSize: 12,

    fontWeight: "700",

    color:
      COMPOFF_THEME.colors.textMuted,
  },

  reason: {
    marginTop: 6,

    fontSize: 14,

    lineHeight: 22,

    color:
      COMPOFF_THEME.colors.textPrimary,
  },

  footer: {
    flexDirection: "row",

    alignItems: "center",

    justifyContent: "space-between",

    marginTop: 18,

    paddingTop: 18,

    borderTopWidth: 1,

    borderTopColor:
      COMPOFF_THEME.colors.divider,
  },

  footerItem: {
    flex: 1,

    flexDirection: "row",

    justifyContent: "center",

    alignItems: "center",
  },

  footerDivider: {
    width: 1,

    height: 36,

    backgroundColor:
      COMPOFF_THEME.colors.divider,
  },

  footerValue: {
    marginLeft: 8,

    fontSize: 14,

    fontWeight: "700",

    color:
      COMPOFF_THEME.colors.textPrimary,
  },

});