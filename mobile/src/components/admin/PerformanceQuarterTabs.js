import React from "react";

import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
} from "react-native";

import PERFORMANCE_THEME from "../../constants/performanceTheme";

const QUARTERS = [
  "Q1",
  "Q2",
  "Q3",
  "Q4",
];

export default function PerformanceQuarterTabs({
  selectedQuarter,
  onChange,
}) {
  return (
    <View style={styles.container}>

      <View style={styles.wrapper}>

        {QUARTERS.map((quarter) => {

          const active =
            selectedQuarter === quarter;

          return (
            <TouchableOpacity
              key={quarter}
              activeOpacity={0.9}
              onPress={() =>
                onChange(quarter)
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
                {quarter}
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
    marginBottom: 22,
  },

  wrapper: {
    flexDirection: "row",

    justifyContent: "space-between",

    backgroundColor: "#EEF2F7",

    padding: 6,

    borderRadius: 22,
  },

  tab: {
    flex: 1,

    height: 50,

    borderRadius: 16,

    justifyContent: "center",

    alignItems: "center",
  },

  activeTab: {
    backgroundColor:
      PERFORMANCE_THEME.colors.primary,

    shadowColor:
      PERFORMANCE_THEME.colors.primary,

    shadowOpacity: 0.18,

    shadowRadius: 10,

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