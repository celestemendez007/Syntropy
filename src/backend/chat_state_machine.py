class ChatStateMachine:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id
        self.state = "START"
        self.barrier = None
        self.selected_offer = None
    
    def transition(self, action: str, data: dict = None):
        """
        Maneja la transición de estados de la conversación.
        """
        if self.state == "START" and action == "USER_REPLIES":
            self.state = "UNDERSTAND"
            
        elif self.state == "UNDERSTAND" and action == "BARRIER_IDENTIFIED":
            self.barrier = data.get("barrier")
            self.state = "PRESENT_OPTIONS"
            
        elif self.state == "PRESENT_OPTIONS" and action == "OFFER_SELECTED":
            self.selected_offer = data.get("offer_id")
            self.state = "CONFIRM"
            
        elif self.state == "CONFIRM" and action == "USER_CONFIRMS":
            self.state = "CLOSE"
            
        elif action == "ESCALATE":
            self.state = "ESCALATED_TO_HUMAN"
            
        return self.state
        
    def get_conversation_result(self) -> dict:
        return {
            "state": self.state,
            "barrier": self.barrier,
            "selected_offer": self.selected_offer,
            "confirmed": self.state == "CLOSE"
        }
