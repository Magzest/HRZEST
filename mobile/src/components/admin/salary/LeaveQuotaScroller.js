import React from "react";

import {
  View,
  Text,
 ScrollView,
  StyleSheet,
} from "react-native";

import { Ionicons } from "@expo/vector-icons";

import LEAVE_THEME from "../../../constants/leaveTheme";

export default function LeaveQuotaScroller({
  balances = [],
}) {
  return (
    <View style={styles.container}>

      <View style={styles.header}>

        <Text style={styles.title}>
          Leave Quotas
        </Text>

        <Text style={styles.subtitle}>
          Remaining leave by category
        </Text>

      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >

        {balances.map((item) => {

          const progress =
            item.total > 0
              ? (item.remaining / item.total) * 100
              : 0;

          return (

            <View
              key={item.id}
              style={styles.card}
            >

              <View
                style={[
                  styles.iconContainer,
                  {
                    backgroundColor:
                      item.color + "20",
                  },
                ]}
              >

                <Ionicons
                  name="briefcase-outline"
                  size={22}
                  color={item.color}
                />

              </View>

              <Text
                numberOfLines={1}
                style={styles.leaveName}
              >
                {item.title}
              </Text>

              <Text style={styles.remaining}>
                {item.remaining}
              </Text>

              <Text style={styles.remainingText}>
                Remaining
              </Text>

              <View style={styles.progressBackground}>

                <View
                  style={[
                    styles.progressFill,
                    {
                      width: `${progress}%`,
                      backgroundColor:
                        item.color,
                    },
                  ]}
                />

              </View>

              <View style={styles.footer}>

                <Text style={styles.footerText}>
                  Used {item.used}
                </Text>

                <Text style={styles.footerText}>
                  Total {item.total}
                </Text>

              </View>

            </View>

          );

        })}

      </ScrollView>

    </View>
  );
}

const styles = StyleSheet.create({

  container: {
    marginBottom: 20,
  },

  header: {
    marginBottom: 14,
  },

  title: {
    fontSize: 18,

    fontWeight: "800",

    color:
      LEAVE_THEME.colors.textPrimary,
  },

  subtitle: {
    marginTop: 4,

    fontSize: 13,

    color:
      LEAVE_THEME.colors.textMuted,
  },

  scrollContent: {
    paddingRight: 18,
  },

  card: {
    width: 170,

    backgroundColor: "#FFFFFF",

    borderRadius: 22,

    padding: 18,

    marginRight: 16,

    borderWidth: 1,

    borderColor:
      LEAVE_THEME.colors.border,

    ...LEAVE_THEME.shadow,
  },

  iconContainer: {
    width: 52,

    height: 52,

    borderRadius: 16,

    justifyContent: "center",

    alignItems: "center",

    marginBottom: 16,
  },

  leaveName: {
    fontSize: 15,

    fontWeight: "700",

    color:
      LEAVE_THEME.colors.textPrimary,
  },

  remaining: {
    marginTop: 14,

    fontSize: 34,

    fontWeight: "800",

    color:
      LEAVE_THEME.colors.textPrimary,
  },

  remainingText: {
    marginTop: 2,

    fontSize: 13,

    color:
      LEAVE_THEME.colors.textMuted,
  },

  progressBackground: {
    height: 8,

    marginTop: 18,

    borderRadius: 8,

    overflow: "hidden",

    backgroundColor:
      LEAVE_THEME.colors.divider,
  },

  progressFill: {
    height: "100%",

    borderRadius: 8,
  },

  footer: {
    flexDirection: "row",

    justifyContent: "space-between",

    marginTop: 14,
  },

  footerText: {
    fontSize: 12,

    fontWeight: "600",

    color:
      LEAVE_THEME.colors.textMuted,
  },

});