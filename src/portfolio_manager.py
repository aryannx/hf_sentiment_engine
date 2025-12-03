# src/portfolio_manager.py
class PortfolioManager:
    def __init__(self, strategies=['equity', 'credit', 'volatility']):
        self.strategies = strategies
        self.risk_limit = 0.02  # 2% max risk per position

    def blend_signals(self, signal_dict, volatility_dict):
        """
        Blend signals into portfolio weights
        Args:
            signal_dict: {'equity': signals_array, 'credit': signals_array}
            volatility_dict: {'equity': vol, 'credit': vol}
        Returns:
            dict: {'equity': 0.4, 'credit': 0.5, 'vol': 0.1}
        """
        # Kelly-like sizing
        weights = {}
        total_signal_strength = 0

        for strat, signals in signal_dict.items():
            strength = np.mean(np.abs(signals))
            vol = volatility_dict[strat]
            kelly_weight = (strength / vol) * 0.01  # Normalize
            weights[strat] = min(kelly_weight, self.risk_limit)
            total_signal_strength += strength

        # Normalize to 100%
        total_weight = sum(weights.values())
        for strat in weights:
            weights[strat] /= total_weight

        return weights

    def calculate_portfolio_sharpe(self, returns_dict, weights):
        """Portfolio-level Sharpe (key fund metric)"""
        blended_returns = np.zeros(min(map(len, returns_dict.values())))
        for strat, returns in returns_dict.items():
            blended_returns += returns * weights[strat]
        return (blended_returns.mean() / blended_returns.std()) * np.sqrt(252)
